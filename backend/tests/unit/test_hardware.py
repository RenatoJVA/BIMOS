"""Unit tests for the hardware detection and feasibility checks."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from bimos.cli.commands.qm import _qm_memory_gb, gaussian_memory_gb
from bimos.shared import hardware
from bimos.shared.hardware import (
    DISK_MIN_BLOCK_GB,
    DISK_MIN_OK_GB,
    RAM_WARN_FRACTION,
    VRAM_MIN_OK_GB,
    VRAM_MIN_WARN_GB,
    DiskInfo,
    GpuInfo,
    Level,
    MemInfo,
    Verdict,
    best_gpu,
    check_cpu,
    check_disk,
    check_ram,
    check_vram,
    detect_cpu,
    detect_disk,
    detect_gpus,
    detect_mem,
    guard,
    parse_nvidia_smi,
    report,
    warn_only,
    worst,
)

RTX_4090 = GpuInfo(name="NVIDIA GeForce RTX 4090", vram_total_gb=24.0, vram_free_gb=23.5)
SMALL_GPU = GpuInfo(name="NVIDIA GTX 1060", vram_total_gb=6.0, vram_free_gb=5.5)
NO_GPU_TEXT = "no NVIDIA GPU visible"


def _gpu(free_gb: float) -> GpuInfo:
    return GpuInfo(name="Test GPU", vram_total_gb=free_gb, vram_free_gb=free_gb)


# --------------------------------------------------------------------------- #
# Level
# --------------------------------------------------------------------------- #
def test_level_exposes_style_and_label() -> None:
    assert Level.OK.style == "green"
    assert Level.OK.label == "viable"
    assert Level.WARN.style == "yellow"
    assert Level.WARN.label == "viable with warnings"
    assert Level.BLOCK.style == "red"
    assert Level.BLOCK.label == "not viable"


# --------------------------------------------------------------------------- #
# nvidia-smi parsing
# --------------------------------------------------------------------------- #
def test_parse_nvidia_smi_single_gpu() -> None:
    gpus = parse_nvidia_smi("NVIDIA GeForce RTX 5090, 32607, 30360\n")
    assert len(gpus) == 1
    assert gpus[0].name == "NVIDIA GeForce RTX 5090"
    assert gpus[0].vram_total_gb == pytest.approx(31.84, abs=0.01)
    assert gpus[0].vram_free_gb == pytest.approx(29.65, abs=0.01)


def test_parse_nvidia_smi_multi_gpu_picks_most_free() -> None:
    text = "GPU A, 8192, 8000\nGPU B, 24576, 24000\n"
    gpus = parse_nvidia_smi(text)
    assert len(gpus) == 2
    assert best_gpu(gpus).name == "GPU B"
    assert best_gpu(gpus).vram_free_gb == pytest.approx(23.44, abs=0.01)


def test_parse_nvidia_smi_ignores_malformed_lines() -> None:
    text = "\nGPU A, 8192, 8000\nbroken, line\nGPU B, notanumber, 100\ngarbage\n"
    assert [g.name for g in parse_nvidia_smi(text)] == ["GPU A"]


def test_parse_nvidia_smi_empty_output() -> None:
    assert parse_nvidia_smi("") == []


def test_detect_gpus_returns_empty_without_nvidia_smi(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware.shutil, "which", lambda _name: None)
    assert detect_gpus() == []


def test_detect_gpus_returns_empty_on_nonzero_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware.shutil, "which", lambda _name: "/usr/bin/nvidia-smi")

    class _Result:
        returncode = 9
        stdout = "should be ignored"

    monkeypatch.setattr(hardware.subprocess, "run", lambda *a, **k: _Result())
    assert detect_gpus() == []


def test_detect_gpus_survives_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware.shutil, "which", lambda _name: "/usr/bin/nvidia-smi")

    def _raise(*_a: object, **_k: object) -> None:
        raise hardware.subprocess.TimeoutExpired(cmd="nvidia-smi", timeout=10)

    monkeypatch.setattr(hardware.subprocess, "run", _raise)
    assert detect_gpus() == []


def test_detect_gpus_uses_nvidia_smi_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware.shutil, "which", lambda _name: "/usr/bin/nvidia-smi")

    class _Result:
        returncode = 0
        stdout = "NVIDIA GeForce RTX 5090, 32607, 30360\n"

    monkeypatch.setattr(hardware.subprocess, "run", lambda *a, **k: _Result())
    gpus = detect_gpus()
    assert [g.name for g in gpus] == ["NVIDIA GeForce RTX 5090"]
    assert gpus[0].vram_free_gb == pytest.approx(29.65, abs=0.01)


def test_best_gpu_of_empty_is_none() -> None:
    assert best_gpu([]) is None


# --------------------------------------------------------------------------- #
# CPU / RAM / disk detection
# --------------------------------------------------------------------------- #
def test_detect_cpu_counts_are_positive() -> None:
    cpu = detect_cpu()
    assert cpu.logical >= 1
    assert cpu.physical >= 1
    assert cpu.physical <= cpu.logical


def test_detect_mem_reads_proc_meminfo() -> None:
    mem = detect_mem()
    if mem is not None:  # pragma: no branch - POSIX CI always has it
        assert mem.total_gb > 0
        assert 0 <= mem.avail_gb <= mem.total_gb


def test_detect_disk_uses_workspace(tmp_path) -> None:
    disk = detect_disk(tmp_path)
    assert disk is not None
    assert disk.free_gb > 0


def test_detect_disk_returns_none_on_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise(_path: object) -> None:
        raise OSError("no such filesystem")

    monkeypatch.setattr(hardware.shutil, "disk_usage", _raise)
    assert detect_disk("/nonexistent-root") is None


# --------------------------------------------------------------------------- #
# check_vram
# --------------------------------------------------------------------------- #
def test_check_vram_missing_gpu_blocks_when_required() -> None:
    verdict = check_vram([], required=True)
    assert verdict.level is Level.BLOCK
    assert "no NVIDIA GPU" in verdict.message


def test_check_vram_missing_gpu_ok_when_not_required() -> None:
    verdict = check_vram([], required=False)
    assert verdict.level is Level.OK


@pytest.mark.parametrize("free", [0.0, 3.9, VRAM_MIN_WARN_GB - 0.1])
def test_check_vram_below_minimum_blocks(free: float) -> None:
    assert check_vram([_gpu(free)]).level is Level.BLOCK


@pytest.mark.parametrize("free", [VRAM_MIN_WARN_GB, 12.0, VRAM_MIN_OK_GB - 0.1])
def test_check_vram_between_min_and_ok_warns(free: float) -> None:
    assert check_vram([_gpu(free)]).level is Level.WARN


@pytest.mark.parametrize("free", [VRAM_MIN_OK_GB, 24.0, 80.0])
def test_check_vram_at_or_above_ok_is_green(free: float) -> None:
    assert check_vram([_gpu(free)]).level is Level.OK


def test_check_vram_uses_most_free_gpu() -> None:
    verdict = check_vram([_gpu(2.0), _gpu(20.0)])
    assert verdict.level is Level.OK


def test_check_vram_message_names_the_gpu() -> None:
    verdict = check_vram([SMALL_GPU])
    assert "GTX 1060" in verdict.message


# --------------------------------------------------------------------------- #
# check_ram
# --------------------------------------------------------------------------- #
def test_check_ram_no_request_is_ok() -> None:
    assert check_ram(None).level is Level.OK
    assert check_ram(0).level is Level.OK


def test_check_ram_unmeasurable_memory_never_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_mem", lambda: None)
    verdict = check_ram(999.0)
    assert verdict.level is Level.OK
    assert "not measurable" in verdict.message


def test_check_ram_above_installed_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_mem", lambda: MemInfo(total_gb=32.0, avail_gb=30.0))
    verdict = check_ram(64.0)
    assert verdict.level is Level.BLOCK
    assert "32 GB of RAM" in verdict.message
    assert "64 GB requested" in verdict.message


def test_check_ram_exactly_installed_warns_not_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """100% of RAM is allowed but above the 70% recommendation."""
    monkeypatch.setattr(hardware, "detect_mem", lambda: MemInfo(total_gb=64.0, avail_gb=60.0))
    assert check_ram(64.0).level is Level.WARN


def test_check_ram_above_seventy_percent_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    total = 100.0
    monkeypatch.setattr(hardware, "detect_mem", lambda: MemInfo(total_gb=total, avail_gb=80.0))
    threshold = total * RAM_WARN_FRACTION
    assert check_ram(threshold - 1.0).level is Level.OK
    assert check_ram(threshold + 1.0).level is Level.WARN


# --------------------------------------------------------------------------- #
# check_cpu
# --------------------------------------------------------------------------- #
def test_check_cpu_no_request_is_ok() -> None:
    assert check_cpu(None).level is Level.OK
    assert check_cpu(0).level is Level.OK


def test_check_cpu_within_physical_cores_is_ok() -> None:
    physical = detect_cpu().physical
    assert check_cpu(physical).level is Level.OK


def test_check_cpu_above_physical_cores_warns() -> None:
    physical = detect_cpu().physical
    assert check_cpu(physical + 8).level is Level.WARN


# --------------------------------------------------------------------------- #
# check_disk
# --------------------------------------------------------------------------- #
def test_check_disk_unmeasurable_is_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_disk", lambda _p=None: None)
    assert check_disk().level is Level.OK


def test_check_disk_below_block_threshold(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_disk", lambda _p=None: DiskInfo(free_gb=DISK_MIN_BLOCK_GB - 0.1))
    assert check_disk().level is Level.BLOCK


def test_check_disk_at_block_threshold_does_not_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Exactly the minimum is runnable, but still below the recommended free space."""
    monkeypatch.setattr(hardware, "detect_disk", lambda _p=None: DiskInfo(free_gb=DISK_MIN_BLOCK_GB))
    assert check_disk().level is Level.WARN


def test_check_disk_between_block_and_ok_warns(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_disk", lambda _p=None: DiskInfo(free_gb=DISK_MIN_OK_GB - 1.0))
    assert check_disk().level is Level.WARN


def test_check_disk_at_ok_threshold_is_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_disk", lambda _p=None: DiskInfo(free_gb=DISK_MIN_OK_GB))
    assert check_disk().level is Level.OK


# --------------------------------------------------------------------------- #
# worst / report
# --------------------------------------------------------------------------- #
def test_worst_of_empty_is_ok() -> None:
    assert worst([]) is Level.OK


def test_worst_picks_block_over_warn() -> None:
    verdicts = [Verdict(Level.OK, "a"), Verdict(Level.WARN, "b"), Verdict(Level.BLOCK, "c")]
    assert worst(verdicts) is Level.BLOCK


def test_worst_picks_warn_over_ok() -> None:
    assert worst([Verdict(Level.OK, "a"), Verdict(Level.WARN, "b")]) is Level.WARN


def test_report_contains_name_level_and_details() -> None:
    line = report("predict", [Verdict(Level.BLOCK, "no GPU")])
    assert "predict" in line
    assert "red" in line
    assert "no GPU" in line


def test_report_marks_forced_only_when_blocked() -> None:
    forced_block = report("predict", [Verdict(Level.BLOCK, "x")], force=True)
    assert "forced" in forced_block
    ok_line = report("predict", [Verdict(Level.OK, "x")], force=True)
    assert "forced" not in ok_line


# --------------------------------------------------------------------------- #
# warn_only / guard
# --------------------------------------------------------------------------- #
def test_warn_only_is_silent_when_ok(capsys: pytest.CaptureFixture[str]) -> None:
    warn_only("predict", [Verdict(Level.OK, "all good")])
    assert capsys.readouterr().out == ""


def test_warn_only_prints_on_warn(capsys: pytest.CaptureFixture[str]) -> None:
    warn_only("dock", [Verdict(Level.WARN, "too many threads")])
    assert "warning" in capsys.readouterr().out


def test_warn_only_never_raises_on_block(capsys: pytest.CaptureFixture[str]) -> None:
    warn_only("predict", [Verdict(Level.BLOCK, "no GPU")])
    assert "no GPU" in capsys.readouterr().out


def test_guard_is_silent_when_ok(capsys: pytest.CaptureFixture[str]) -> None:
    guard("predict", [Verdict(Level.OK, "fine")])
    assert capsys.readouterr().out == ""


def test_guard_warns_but_continues_on_warn(capsys: pytest.CaptureFixture[str]) -> None:
    guard("dock", [Verdict(Level.WARN, "contended")])
    assert "warning" in capsys.readouterr().out


def test_guard_blocks_on_red() -> None:
    import click

    with pytest.raises(click.ClickException) as excinfo:
        guard("predict", [Verdict(Level.BLOCK, NO_GPU_TEXT)])
    assert NO_GPU_TEXT in str(excinfo.value)
    assert "--force" in str(excinfo.value)
    assert "doctor" in str(excinfo.value)


def test_guard_allows_forced_block(capsys: pytest.CaptureFixture[str]) -> None:
    guard("predict", [Verdict(Level.BLOCK, NO_GPU_TEXT)], force=True)
    out = capsys.readouterr().out
    assert "warning" in out
    assert "forced" in out


# --------------------------------------------------------------------------- #
# per-process assessors
# --------------------------------------------------------------------------- #
def test_assess_boltz_requires_gpu() -> None:
    assert hardware.assess_boltz([])[0].level is Level.BLOCK
    assert hardware.assess_boltz([RTX_4090])[0].level is Level.OK


def test_assess_boltz_small_gpu_warns() -> None:
    assert hardware.assess_boltz([SMALL_GPU])[0].level is Level.BLOCK
    assert hardware.assess_boltz([_gpu(12.0)])[0].level is Level.WARN


def test_assess_dock_reads_vina_threads() -> None:
    verdicts = hardware.assess_dock({"vina": {"cpu_per_job": 1}})
    assert verdicts[0].level is Level.OK
    over = hardware.assess_dock({"vina": {"cpu_per_job": 4096}})
    assert over[0].level is Level.WARN


def test_assess_dock_tolerates_empty_config() -> None:
    assert hardware.assess_dock(None)[0].level is Level.OK
    assert hardware.assess_dock({})[0].level is Level.OK


def test_assess_md_checks_cpu_and_disk() -> None:
    verdicts = hardware.assess_md()
    assert len(verdicts) == 3
    assert worst(verdicts) in {Level.OK, Level.WARN, Level.BLOCK}
    assert any("workspace" in v.message or "measurable" in v.message for v in verdicts)


def test_assess_qm_blocks_when_total_exceeds_ram(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_mem", lambda: MemInfo(total_gb=16.0, avail_gb=15.0))
    assert worst(hardware.assess_qm(32.0, 4)) is Level.BLOCK


def test_assess_qm_green_for_small_request(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(hardware, "detect_mem", lambda: MemInfo(total_gb=256.0, avail_gb=200.0))
    assert worst(hardware.assess_qm(4.0, 1)) is Level.OK


def test_assess_qm_without_memory_value_is_ok() -> None:
    assert worst(hardware.assess_qm(None, 1)) is Level.OK


def test_assess_qm_does_not_require_gpu() -> None:
    assert worst(hardware.assess_qm(1.0, 1, [])) is Level.OK


def test_assess_screen_includes_qm_checks() -> None:
    verdicts = hardware.assess_screen(2.0, 1, [])
    assert len(verdicts) >= 4
    assert worst(verdicts) in {Level.OK, Level.WARN, Level.BLOCK}


def test_assess_screen_never_blocks_on_missing_gpu() -> None:
    assert worst(hardware.assess_screen(2.0, 1, [])) is not Level.BLOCK


# --------------------------------------------------------------------------- #
# snapshot
# --------------------------------------------------------------------------- #
def test_snapshot_exposes_all_resources_and_thresholds() -> None:
    snap = hardware.snapshot()
    assert snap["cpu"].physical >= 1
    assert "mem" in snap and "disk" in snap and "gpus" in snap
    thresholds = snap["thresholds"]
    assert thresholds["vram_min_ok_gb"] == VRAM_MIN_OK_GB
    assert thresholds["vram_min_warn_gb"] == VRAM_MIN_WARN_GB
    assert thresholds["ram_warn_fraction"] == RAM_WARN_FRACTION
    assert thresholds["disk_min_ok_gb"] == DISK_MIN_OK_GB
    assert thresholds["disk_min_block_gb"] == DISK_MIN_BLOCK_GB


# --------------------------------------------------------------------------- #
# Gaussian mem parsing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("32GB", 32.0),          # the packaged default
        ("32gb", 32.0),
        ("32000MB", 31.25),
        ("32000mb", 31.25),
        ("32000", 31.25),        # a bare number means MB in Gaussian
        ("4 GB", 4.0),           # internal whitespace
        ("1.5GW", 1.5),
        ("32000MW", 31.25),
    ],
)
def test_gaussian_mem_is_parsed_with_its_unit(value: str, expected: float) -> None:
    """Regression guard: the unit suffix used to be discarded.

    Reading 32GB as 32/1024 GB under-reported the request by 1024x, so the
    qm-g16 guard could never block on the default configuration.
    """
    assert gaussian_memory_gb(value) == pytest.approx(expected)


@pytest.mark.parametrize("value", ["", None, "GB", "abc", "32TB", "32 GB extra"])
def test_gaussian_mem_rejects_unparseable_values(value: object) -> None:
    assert gaussian_memory_gb(value) is None


def test_qm_memory_uses_the_selected_backend() -> None:
    """``_qm_memory_gb`` must not read ORCA settings for a Gaussian request."""
    configs = {
        "orca": {"orca": {"maxcore_mb": 32000}},
        "gaussian": {"gaussian": {"mem": "32GB"}},
    }
    with patch(
        "bimos.shared.user_config.resolve", side_effect=lambda name: (configs[name], {})
    ):
        assert _qm_memory_gb("orca") == pytest.approx(31.25)
        assert _qm_memory_gb("gaussian") == pytest.approx(32.0)
