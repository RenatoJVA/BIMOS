"""``bimos doctor``: report detected hardware and per-process feasibility."""

from __future__ import annotations

from typing import Any

import rich_click as click
from rich.console import Console
from rich.table import Table

from bimos.shared import hardware
from bimos.shared.hardware import Level, Verdict

DOCTOR_EPILOG = """
[b green]Green[/]: the machine supports the current configuration as-is.
[b yellow]Yellow[/]: it will run, but the current values are above what is
recommended; lower them for headroom.
[b red]Red[/]: it will very likely fail. Pass [b]--force[/] to run anyway.

Thresholds (heuristics): GPU {vram_warn} GB minimum / {vram_ok} GB recommended,
RAM above {ram_pct}% of installed memory, workspace disk {disk_block} GB minimum
/ {disk_ok} GB recommended.
""".strip()


def _fmt(value: Any, suffix: str, digits: int = 1) -> str:
    if value is None:
        return "not measurable"
    return f"{value:.{digits}f} {suffix}"


def _qm_memory_gb(name: str) -> float | None:
    """Requested RAM per QM job, in GB, from the user or packaged config.

    Delegates to the QM command so both read the same units; this used to be a
    second copy that stripped the unit suffix and reported 32GB as 0.03 GB.
    """
    from bimos.cli.commands.qm import _qm_memory_gb as read_memory

    return read_memory(name)


def _config_jobs(name: str) -> int:
    from bimos.shared.user_config import resolve

    try:
        data, _ = resolve(name)
    except (OSError, ValueError, KeyError):
        return 2
    section = data.get("orca") if name == "orca" else data.get("gaussian", {})
    return int((section or {}).get("max_jobs", 2))


def _rows() -> list[tuple[str, list[Verdict]]]:
    """One assessment row per process, using the active configuration."""
    from bimos.shared.user_config import resolve

    gpus = hardware.detect_gpus()

    try:
        docking, _ = resolve("docking")
    except (OSError, ValueError, KeyError):
        docking = None

    rows: list[tuple[str, list[Verdict]]] = [
        ("predict / predict-boltz", hardware.assess_boltz(gpus)),
        ("dock", hardware.assess_dock(docking)),
        ("workflow (MD)", hardware.assess_md()),
    ]
    # ORCA and Gaussian are configured separately, so each row is graded against
    # its own backend rather than a shared default.
    screen_gb = _qm_memory_gb("orca")
    screen_jobs = _config_jobs("orca")
    rows.append(
        ("screen (dock + QM + MD)", hardware.assess_screen(screen_gb, screen_jobs, gpus, docking))
    )
    rows.append(("qm-orca", hardware.assess_qm(screen_gb, screen_jobs, gpus)))
    gaussian_gb = _qm_memory_gb("gaussian")
    rows.append(("qm-g16", hardware.assess_qm(gaussian_gb, _config_jobs("gaussian"), gpus)))
    return rows


def _hardware_table(snap: dict[str, Any]) -> Table:
    table = Table(title="Detected hardware", show_header=True, header_style="bold")
    table.add_column("Resource")
    table.add_column("Value", overflow="fold")

    cpu = snap["cpu"]
    table.add_row("CPU", f"{cpu.physical} physical / {cpu.logical} logical cores")
    mem = snap["mem"]
    if mem is None:
        table.add_row("RAM", "[yellow]not measurable[/]")
    else:
        table.add_row(
            "RAM", f"{mem.total_gb:.1f} GB total, {mem.avail_gb:.1f} GB available"
        )
    disk = snap["disk"]
    table.add_row(
        "Disk (workspace)",
        f"{disk.free_gb:.1f} GB free" if disk else "[yellow]not measurable[/]",
    )
    gpus = snap["gpus"]
    if gpus:
        for gpu in gpus:
            table.add_row(
                f"GPU ({gpu.name})",
                f"{gpu.vram_total_gb:.1f} GB VRAM total, "
                f"{gpu.vram_free_gb:.1f} GB free",
            )
    else:
        table.add_row("GPU", "[red]no NVIDIA GPU detected[/]")
    return table


def _process_table(rows: list[tuple[str, list[Verdict]]]) -> Table:
    table = Table(title="Process feasibility", show_header=True, header_style="bold")
    table.add_column("Process")
    table.add_column("Verdict")
    table.add_column("Details", overflow="fold")
    for name, verdicts in rows:
        level = hardware.worst(verdicts)
        table.add_row(
            name,
            f"[bold {level.style}]{level.label}[/]",
            "\n".join(f"- {v.message}" for v in verdicts),
        )
    return table


def _thresholds_table(snap: dict[str, Any]) -> Table:
    table = Table(title="Thresholds in use", show_header=True, header_style="bold")
    table.add_column("Check")
    table.add_column("Yellow below")
    table.add_column("Red below")
    t = snap["thresholds"]
    table.add_row("GPU VRAM (free)", f"{t['vram_min_ok_gb']:.0f} GB", f"{t['vram_min_warn_gb']:.0f} GB")
    table.add_row(
        "RAM requested",
        f"{t['ram_warn_fraction'] * 100:.0f}% of installed",
        "100% of installed",
    )
    table.add_row(
        "Disk (workspace, free)",
        f"{t['disk_min_ok_gb']:.0f} GB",
        f"{t['disk_min_block_gb']:.0f} GB",
    )
    return table


@click.command("doctor", epilog=DOCTOR_EPILOG)
@click.option("--json", "as_json", is_flag=True, help="Emit the report as JSON.")
def doctor(as_json: bool) -> None:
    """
    Check whether this machine can run the BIMOS processes.

    Detects CPU cores, RAM, workspace disk and NVIDIA GPUs, then grades every
    process (green / yellow / red) against the active configuration. Read-only:
    nothing is launched and no file is modified.
    """
    snap = hardware.snapshot()
    rows = _rows()
    blocked = [name for name, verdicts in rows if hardware.worst(verdicts) is Level.BLOCK]

    if as_json:
        import json

        payload = {
            "cpu": {
                "physical": snap["cpu"].physical,
                "logical": snap["cpu"].logical,
            },
            "memory_gb": None
            if snap["mem"] is None
            else {
                "total": round(snap["mem"].total_gb, 2),
                "available": round(snap["mem"].avail_gb, 2),
            },
            "disk_free_gb": None
            if snap["disk"] is None
            else round(snap["disk"].free_gb, 2),
            "gpus": [
                {
                    "name": g.name,
                    "vram_total_gb": round(g.vram_total_gb, 2),
                    "vram_free_gb": round(g.vram_free_gb, 2),
                }
                for g in snap["gpus"]
            ],
            "thresholds": snap["thresholds"],
            "viable": not blocked,
            "blocked_processes": blocked,
            "processes": [
                {
                    "process": name,
                    "level": str(hardware.worst(verdicts)),
                    "message": hardware.report(name, verdicts).split(" - ", 1)[-1],
                    "checks": [
                        {"level": str(v.level), "message": v.message} for v in verdicts
                    ],
                }
                for name, verdicts in rows
            ],
        }
        # Nothing else may be printed: consumers pipe this into jq.
        click.echo(json.dumps(payload, indent=2))
        return

    console = Console()
    console.print(_hardware_table(snap))
    console.print(_process_table(rows))
    console.print(_thresholds_table(snap))

    if blocked:
        console.print(
            "\n[b red]Some processes are not viable here.[/] "
            "Pass [b]--force[/] to override the guardrail, or lower the values "
            "in [b]~/.bimos/config[/]."
        )
