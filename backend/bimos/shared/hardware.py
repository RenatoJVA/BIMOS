"""
Hardware detection and per-process feasibility checks.

The goal is a traffic light for every process BIMOS can launch:

  * ``OK``    - the machine comfortably supports the requested configuration.
  * ``WARN``  - it will run, but the configuration is above what is recommended.
  * ``BLOCK`` - it will very likely fail (OOM killer, CUDA OOM, no device).

Rules of the design:

  * Missing data never blocks. If we cannot measure something we degrade to
    ``OK`` so an unknown machine is not penalised.
  * The only hard requirement is the one already enforced by the pipelines
    themselves (Boltz needs a visible NVIDIA GPU).
  * Thresholds are heuristics, documented in ``docs/cli.md`` and MANUAL.md.
  * Blocking is a CLI-level guardrail only: the HTTP API dispatches the same
    pipelines without it, so the web UI keeps its current behaviour.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from bimos.config.settings import settings

# --------------------------------------------------------------------------- #
# Thresholds (heuristics, see docs/cli.md)
# --------------------------------------------------------------------------- #
VRAM_MIN_OK_GB = 16.0
VRAM_MIN_WARN_GB = 8.0
RAM_WARN_FRACTION = 0.7
DISK_MIN_OK_GB = 50.0
DISK_MIN_BLOCK_GB = 10.0

_BYTES_PER_GB = 1024**3


class Level(StrEnum):
    """Severity of a single check."""

    OK = "ok"
    WARN = "warn"
    BLOCK = "block"

    @property
    def style(self) -> str:
        return _LEVEL_STYLE[self][0]

    @property
    def label(self) -> str:
        return _LEVEL_STYLE[self][1]


LEVEL_ORDER = {Level.OK: 0, Level.WARN: 1, Level.BLOCK: 2}

_LEVEL_STYLE = {
    Level.OK: ("green", "viable"),
    Level.WARN: ("yellow", "viable with warnings"),
    Level.BLOCK: ("red", "not viable"),
}


# --------------------------------------------------------------------------- #
# Detected hardware
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CpuInfo:
    logical: int
    physical: int


@dataclass(frozen=True)
class MemInfo:
    total_gb: float
    avail_gb: float


@dataclass(frozen=True)
class GpuInfo:
    name: str
    vram_total_gb: float
    vram_free_gb: float


@dataclass(frozen=True)
class DiskInfo:
    free_gb: float


@dataclass(frozen=True)
class Verdict:
    """Outcome of one check."""

    level: Level
    message: str


# --------------------------------------------------------------------------- #
# Detection
# --------------------------------------------------------------------------- #
def detect_cpu() -> CpuInfo:
    """Physical and logical CPU core counts."""
    logical = os.cpu_count() or 1
    return CpuInfo(logical=logical, physical=settings._physical_core_count())


def _mem_from_proc() -> MemInfo | None:
    try:
        fields: dict[str, int] = {}
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, _, rest = line.partition(":")
            value = rest.strip().split(" ", 1)[0]
            if value.isdigit():
                fields[key] = int(value)
        total_kb = fields.get("MemTotal")
        avail_kb = fields.get("MemAvailable", fields.get("MemFree"))
        if total_kb is None or avail_kb is None:
            return None
        return MemInfo(total_gb=total_kb / 1024**2, avail_gb=avail_kb / 1024**2)
    except (OSError, ValueError):
        return None


def _mem_from_sysconf() -> MemInfo | None:
    try:
        total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        avail = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")
    except (AttributeError, ValueError, OSError):
        return None
    return MemInfo(total_gb=total / _BYTES_PER_GB, avail_gb=avail / _BYTES_PER_GB)


def detect_mem() -> MemInfo | None:
    """Total and available RAM, or ``None`` when it cannot be measured."""
    return _mem_from_proc() or _mem_from_sysconf()


def detect_disk(path: str | Path | None = None) -> DiskInfo | None:
    """Free space on the filesystem holding *path* (defaults to the workspace)."""
    target = Path(path) if path is not None else settings.workspace_path
    probe = target
    while not probe.exists() and probe != probe.parent:
        probe = probe.parent
    try:
        return DiskInfo(free_gb=shutil.disk_usage(probe).free / _BYTES_PER_GB)
    except OSError:
        return None


def _nvidia_query() -> str | None:
    binary = shutil.which("nvidia-smi")
    if binary is None:
        return None
    try:
        result = subprocess.run(  # noqa: S603
            [
                binary,
                "--query-gpu=name,memory.total,memory.free",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return result.stdout


_NVIDIA_FIELDS = 3


def parse_nvidia_smi(stdout: str) -> list[GpuInfo]:
    """Parse ``nvidia-smi`` CSV output into :class:`GpuInfo` records."""
    gpus: list[GpuInfo] = []
    for line in stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != _NVIDIA_FIELDS:
            continue
        name, total, free = parts
        try:
            gpus.append(
                GpuInfo(
                    name=name,
                    vram_total_gb=int(total) / 1024,
                    vram_free_gb=int(free) / 1024,
                )
            )
        except ValueError:
            continue
    return gpus


def detect_gpus() -> list[GpuInfo]:
    """All visible NVIDIA GPUs; empty list when there is none."""
    stdout = _nvidia_query()
    if stdout is None:
        return []
    return parse_nvidia_smi(stdout)


def best_gpu(gpus: Iterable[GpuInfo] | None = None) -> GpuInfo | None:
    """The GPU with the most free VRAM, if any."""
    candidates = list(gpus) if gpus is not None else detect_gpus()
    if not candidates:
        return None
    return max(candidates, key=lambda gpu: gpu.vram_free_gb)


# --------------------------------------------------------------------------- #
# Generic checks
# --------------------------------------------------------------------------- #
def check_vram(
    gpus: Iterable[GpuInfo] | None = None, *, required: bool = True
) -> Verdict:
    """VRAM suitability. *required* adds the hard "no GPU at all" block."""
    gpu = best_gpu(gpus)
    if gpu is None:
        if required:
            return Verdict(
                Level.BLOCK,
                "no NVIDIA GPU visible. Check the driver, then pass the device into "
                "the container (podman: --device nvidia.com/gpu=all).",
            )
        return Verdict(Level.OK, "no NVIDIA GPU visible (not required for this process)")

    free = gpu.vram_free_gb
    if free < VRAM_MIN_WARN_GB:
        return Verdict(
            Level.BLOCK,
            f"{gpu.name}: {free:.1f} GB VRAM free, need "
            f"{VRAM_MIN_WARN_GB:.0f} GB minimum. Close other GPU apps or lower "
            f"--models/-n and --max-parallel-samples.",
        )
    if free < VRAM_MIN_OK_GB:
        return Verdict(
            Level.WARN,
            f"{gpu.name}: {free:.1f} GB VRAM free. Workable, but below the "
            f"{VRAM_MIN_OK_GB:.0f} GB recommended for max settings; reduce "
            f"--models/-n or --max-parallel-samples for headroom.",
        )
    return Verdict(Level.OK, f"{gpu.name}: {free:.1f} GB VRAM free")


def check_ram(requested_gb: float | None) -> Verdict:
    """Compare a requested memory footprint against installed RAM."""
    if not requested_gb or requested_gb <= 0:
        return Verdict(Level.OK, "no explicit memory request")
    mem = detect_mem()
    if mem is None:
        return Verdict(Level.OK, f"{requested_gb:.0f} GB requested (RAM not measurable)")
    if requested_gb > mem.total_gb:
        return Verdict(
            Level.BLOCK,
            f"{requested_gb:.0f} GB requested but the machine has only "
            f"{mem.total_gb:.0f} GB of RAM. Lower the memory value in "
            f"~/.bimos/config, reduce --jobs, or use a bigger host.",
        )
    if requested_gb > mem.total_gb * RAM_WARN_FRACTION:
        return Verdict(
            Level.WARN,
            f"{requested_gb:.0f} GB requested uses more than "
            f"{int(RAM_WARN_FRACTION * 100)}% of {mem.total_gb:.0f} GB RAM "
            f"({mem.avail_gb:.0f} GB free). Avoid --jobs above "
            f"{max(1, int(mem.total_gb // requested_gb))}.",
        )
    return Verdict(
        Level.OK,
        f"{requested_gb:.0f} GB requested of {mem.total_gb:.0f} GB RAM "
        f"({mem.avail_gb:.0f} GB free)",
    )


def check_cpu(threads: int | None) -> Verdict:
    """Compare requested threads against physical cores."""
    if not threads or threads <= 0:
        return Verdict(Level.OK, "no explicit thread request")
    cpu = detect_cpu()
    if threads > cpu.physical:
        return Verdict(
            Level.WARN,
            f"{threads} threads requested on {cpu.physical} physical cores "
            f"({cpu.logical} logical). Expect contention; lower the value or "
            f"drop --max.",
        )
    return Verdict(
        Level.OK, f"{threads} threads on {cpu.physical} physical cores"
    )


def check_disk(path: str | Path | None = None) -> Verdict:
    """Free space on the output filesystem."""
    disk = detect_disk(path)
    if disk is None:
        return Verdict(Level.OK, "disk space not measurable")
    if disk.free_gb < DISK_MIN_BLOCK_GB:
        return Verdict(
            Level.BLOCK,
            f"only {disk.free_gb:.1f} GB free on the workspace filesystem, "
            f"need at least {DISK_MIN_BLOCK_GB:.0f} GB. Free space or point "
            f"BIMOS_WORKSPACE elsewhere.",
        )
    if disk.free_gb < DISK_MIN_OK_GB:
        return Verdict(
            Level.WARN,
            f"{disk.free_gb:.1f} GB free on the workspace filesystem; "
            f"{DISK_MIN_OK_GB:.0f} GB is recommended to keep long trajectories "
            f"and screening cascades.",
        )
    return Verdict(Level.OK, f"{disk.free_gb:.1f} GB free on the workspace")


# --------------------------------------------------------------------------- #
# Per-process checks
# --------------------------------------------------------------------------- #
def assess_boltz(gpus: Iterable[GpuInfo] | None = None) -> list[Verdict]:
    """``predict`` / ``predict-boltz``: GPU VRAM is the only hard requirement."""
    return [check_vram(gpus, required=True)]


def assess_dock(config: dict[str, Any] | None = None) -> list[Verdict]:
    """``dock``: CPU threads and workspace disk."""
    threads = None
    if config:
        threads = config.get("vina", {}).get("cpu_per_job")
    return [check_cpu(threads), check_disk()]


def assess_md() -> list[Verdict]:
    """``workflow``: CPU threads and workspace disk (no GPU hard requirement)."""
    return [check_cpu(settings.get_threads()), check_ram(None), check_disk()]


def assess_qm(
    memory_gb: float | None, jobs: int, gpus: Iterable[GpuInfo] | None = None
) -> list[Verdict]:
    """``qm-orca`` / ``qm-g16``: RAM per job and parallelism."""
    per_job = memory_gb if memory_gb else None
    total = per_job * jobs if per_job else None
    return [check_ram(per_job), check_ram(total), check_cpu(jobs), check_vram(gpus, required=False)]


def assess_screen(
    memory_gb: float | None,
    jobs: int,
    gpus: Iterable[GpuInfo] | None = None,
    docking_config: dict[str, Any] | None = None,
) -> list[Verdict]:
    """``screen``: docking + QM + the MD stage that follows (GPU optional).

    *docking_config* is the resolved ``docking`` config, so the Vina thread
    count is checked against the cores the cascade will actually ask for.
    """
    verdicts = assess_dock(docking_config)
    verdicts += assess_qm(memory_gb, jobs, gpus)
    verdicts += [check_disk()]
    return verdicts


# --------------------------------------------------------------------------- #
# Aggregation and reporting
# --------------------------------------------------------------------------- #
def worst(verdicts: Iterable[Verdict]) -> Level:
    """Highest level across *verdicts* (``OK`` when empty)."""
    return max((v.level for v in verdicts), key=lambda lvl: LEVEL_ORDER[lvl], default=Level.OK)


def _level_label(level: Level) -> str:
    return f"[bold {level.style}]{level.label}[/]"


def report(name: str, verdicts: Iterable[Verdict], *, force: bool = False) -> str:
    """One Rich-markup line: process name, worst level and every message."""
    items = list(verdicts)
    level = worst(items)
    suffix = " (forced)" if force and level is Level.BLOCK else ""
    details = "; ".join(v.message for v in items)
    return f"{name}: {_level_label(level)}{suffix} - {details}"


def echo_markup(markup: str) -> None:
    """Print Rich markup; colour is dropped automatically off a terminal."""
    from rich.console import Console

    Console().print(markup)


def warn_only(process: str, verdicts: Iterable[Verdict], *, force: bool = False) -> None:
    """Emit warnings for *process* without ever aborting."""
    items = list(verdicts)
    level = worst(items)
    if level is Level.OK:
        return
    echo_markup(f"[yellow]warning:[/] {report(process, items, force=force)}")


def guard(process: str, verdicts: Iterable[Verdict], *, force: bool = False) -> None:
    """CLI guardrail: warn on WARN, abort on BLOCK unless *force*."""
    from click import ClickException

    items = list(verdicts)
    level = worst(items)
    if level is Level.OK:
        return
    message = report(process, items, force=force)
    if level is Level.BLOCK and not force:
        raise ClickException(
            f"{message}\nRun [bold]bimos doctor[/] for details or pass "
            f"[bold]--force[/] to run anyway."
        )
    echo_markup(f"[yellow]warning:[/] {message}")


def snapshot() -> dict[str, Any]:
    """Detected hardware, used by ``bimos doctor``.

    Deliberately not cached: a transient driver or container-runtime failure
    must not be remembered for the lifetime of a long-running process.
    """
    gpus = detect_gpus()
    return {
        "cpu": detect_cpu(),
        "mem": detect_mem(),
        "disk": detect_disk(),
        "gpus": gpus,
        "thresholds": {
            "vram_min_ok_gb": VRAM_MIN_OK_GB,
            "vram_min_warn_gb": VRAM_MIN_WARN_GB,
            "ram_warn_fraction": RAM_WARN_FRACTION,
            "disk_min_ok_gb": DISK_MIN_OK_GB,
            "disk_min_block_gb": DISK_MIN_BLOCK_GB,
        },
    }
