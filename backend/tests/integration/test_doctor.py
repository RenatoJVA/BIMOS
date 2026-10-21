"""Integration tests for the ``bimos doctor`` command and the hardware guardrail."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner, Result

from bimos.cli.main import cli
from bimos.shared import hardware
from bimos.shared.hardware import DiskInfo, GpuInfo, MemInfo

GOOD_GPU = GpuInfo(name="NVIDIA GeForce RTX 4090", vram_total_gb=24.0, vram_free_gb=23.0)
TINY_GPU = GpuInfo(name="NVIDIA GTX 1060", vram_total_gb=6.0, vram_free_gb=5.0)


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner(env={"COLUMNS": "200", "TERM": "dumb"})


def _patch_hardware(
    *,
    gpus: list[GpuInfo] | None = None,
    total_gb: float = 256.0,
    free_gb: float = 500.0,
) -> object:
    return (
        patch.object(hardware, "detect_gpus", return_value=list(gpus or [])),
        patch.object(
            hardware, "detect_mem", return_value=MemInfo(total_gb=total_gb, avail_gb=total_gb - 4)
        ),
        patch.object(hardware, "detect_disk", return_value=DiskInfo(free_gb=free_gb)),
        patch.object(hardware, "detect_cpu", return_value=hardware.CpuInfo(logical=32, physical=16)),
    )


# --------------------------------------------------------------------------- #
# doctor
# --------------------------------------------------------------------------- #
def test_doctor_is_registered(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "doctor" in result.output


def test_doctor_reports_detected_hardware(runner: CliRunner) -> None:
    patches = _patch_hardware(gpus=[GOOD_GPU])
    for p in patches:
        p.start()
    try:
        result = runner.invoke(cli, ["doctor"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0, result.output
    assert "Detected hardware" in result.output
    assert "NVIDIA GeForce RTX 4090" in result.output
    assert "Process feasibility" in result.output
    assert "Thresholds in use" in result.output


def test_doctor_all_green_on_capable_machine(runner: CliRunner) -> None:
    patches = _patch_hardware(gpus=[GOOD_GPU])
    for p in patches:
        p.start()
    try:
        result = runner.invoke(cli, ["doctor"])
    finally:
        for p in patches:
            p.stop()

    assert "not viable here" not in result.output
    assert "no NVIDIA GPU detected" not in result.output


def test_doctor_flags_missing_gpu(runner: CliRunner) -> None:
    patches = _patch_hardware(gpus=[])
    for p in patches:
        p.start()
    try:
        result = runner.invoke(cli, ["doctor"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0
    assert "no NVIDIA GPU detected" in result.output
    assert "Some processes are not viable here" in result.output
    assert "--force" in result.output


def test_doctor_flags_low_vram(runner: CliRunner) -> None:
    patches = _patch_hardware(gpus=[TINY_GPU])
    for p in patches:
        p.start()
    try:
        result = runner.invoke(cli, ["doctor"])
    finally:
        for p in patches:
            p.stop()

    assert "not viable here" in result.output
    assert "VRAM" in result.output


def test_doctor_flags_small_disk(runner: CliRunner) -> None:
    patches = _patch_hardware(gpus=[GOOD_GPU], free_gb=5.0)
    for p in patches:
        p.start()
    try:
        result = runner.invoke(cli, ["doctor"])
    finally:
        for p in patches:
            p.stop()

    assert "not viable here" in result.output


def test_doctor_json_output_is_valid(runner: CliRunner) -> None:
    patches = _patch_hardware(gpus=[GOOD_GPU])
    for p in patches:
        p.start()
    try:
        result = runner.invoke(cli, ["doctor", "--json"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["cpu"]["physical"] == 16
    assert payload["gpus"][0]["name"] == "NVIDIA GeForce RTX 4090"
    assert payload["thresholds"]["vram_min_warn_gb"] == 8.0
    names = {entry["process"] for entry in payload["processes"]}
    assert {"predict / predict-boltz", "dock", "workflow (MD)"} <= names
    for entry in payload["processes"]:
        assert entry["level"] in {"ok", "warn", "block"}
        assert entry["checks"]


def test_doctor_is_read_only(runner: CliRunner, tmp_path) -> None:
    """doctor must not create files in the workspace."""
    patches = _patch_hardware(gpus=[GOOD_GPU])
    for p in patches:
        p.start()
    try:
        with patch.object(hardware.settings, "workspace_path", tmp_path):
            result = runner.invoke(cli, ["doctor"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------- #
# guard behaviour through the CLI
# --------------------------------------------------------------------------- #
@pytest.fixture
def fake_store() -> MagicMock:
    store = MagicMock()
    store.create.return_value = MagicMock(id="guard_test_job")
    return store


def test_predict_blocks_without_gpu(runner: CliRunner, fake_store: MagicMock, tmp_path) -> None:
    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">x\nMKTA\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[])
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.prediction.predict_boltz") as predict_mock,
        ):
            result = runner.invoke(cli, ["predict", str(fasta)])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code != 0
    assert "no NVIDIA GPU" in result.output
    assert "--force" in result.output
    predict_mock.assert_not_called()


def test_predict_force_runs_without_gpu(runner: CliRunner, fake_store: MagicMock, tmp_path) -> None:
    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">x\nMKTA\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[])
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.prediction.predict_boltz") as predict_mock,
        ):
            predict_mock.return_value = {
                "status": "ok",
                "struct_file": "out.cif",
                "confidence": 0.9,
            }
            result = runner.invoke(cli, ["predict", str(fasta), "--force"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0, result.output
    assert predict_mock.called
    assert "forced" in result.output


def test_predict_silent_when_viable(runner: CliRunner, fake_store: MagicMock, tmp_path) -> None:
    """No warning noise in the common green case."""
    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">x\nMKTA\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[GOOD_GPU])
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.prediction.predict_boltz") as predict_mock,
        ):
            predict_mock.return_value = {
                "status": "ok",
                "struct_file": "out.cif",
                "confidence": 0.9,
            }
            result = runner.invoke(cli, ["predict", str(fasta)])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0, result.output
    assert "warning" not in result.output
    assert "Job ID" in result.output


def test_predict_boltz_alias_shares_the_guard(runner: CliRunner, fake_store: MagicMock, tmp_path) -> None:
    fasta = tmp_path / "seq.fasta"
    fasta.write_text(">x\nMKTA\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[])
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.prediction.predict_boltz") as predict_mock,
        ):
            result = runner.invoke(cli, ["predict-boltz", str(fasta)])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code != 0
    predict_mock.assert_not_called()


def test_dock_blocks_on_tiny_disk(runner: CliRunner, fake_store: MagicMock, tmp_path) -> None:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text("ATOM\n", encoding="utf-8")
    sdf = tmp_path / "lig.sdf"
    sdf.write_text("lig\n\n\n$$$$\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[GOOD_GPU], free_gb=2.0)
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.docking.run_docking_pipeline") as dock_mock,
        ):
            result = runner.invoke(cli, ["dock", str(pdb), str(sdf)])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code != 0
    assert "GB free" in result.output
    dock_mock.assert_not_called()


def test_dock_force_runs_on_tiny_disk(runner: CliRunner, fake_store: MagicMock, tmp_path) -> None:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text("ATOM\n", encoding="utf-8")
    sdf = tmp_path / "lig.sdf"
    sdf.write_text("lig\n\n\n$$$$\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[GOOD_GPU], free_gb=2.0)
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.docking.run_docking_pipeline") as dock_mock,
        ):
            dock_mock.return_value = {"status": "ok", "output_dir": str(tmp_path / "out")}
            result = runner.invoke(cli, ["dock", str(pdb), str(sdf), "--force"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0, result.output
    assert dock_mock.called


def test_qm_orca_blocks_when_ram_is_insufficient(
    runner: CliRunner, fake_store: MagicMock, tmp_path
) -> None:
    ligands = tmp_path / "ligands"
    ligands.mkdir()
    (ligands / "JZ4.gro").write_text("x\n", encoding="utf-8")
    (ligands / "JZ4.itp").write_text("x\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[GOOD_GPU], total_gb=8.0)
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.quantum_chemistry.run_orca_pipeline") as orca_mock,
            patch("bimos.cli.commands.qm._require_qm_toolchain"),
            patch(
                "bimos.cli.commands.qm._qm_memory_gb",
                return_value=32.0,
            ),
        ):
            result = runner.invoke(cli, ["qm-orca", str(ligands), "-j", "4"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code != 0
    assert "RAM" in result.output
    orca_mock.assert_not_called()


def test_workflow_warns_but_runs_on_low_disk(
    runner: CliRunner, fake_store: MagicMock, tmp_path
) -> None:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text("ATOM\n", encoding="utf-8")

    patches = _patch_hardware(gpus=[], free_gb=20.0)
    for p in patches:
        p.start()
    try:
        with (
            patch("bimos.infrastructure.job_store.store", fake_store),
            patch("bimos.molecular_dynamics.run_md_simulation") as md_mock,
        ):
            md_mock.return_value = {"status": "ok", "output_dir": str(tmp_path / "md")}
            result = runner.invoke(cli, ["workflow", "--protein", str(pdb)])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0, result.output
    assert "warning" in result.output
    assert md_mock.called


def test_force_flag_present_in_every_pipeline_help(runner: CliRunner) -> None:
    for command in ("predict", "predict-boltz", "dock", "workflow", "screen", "qm-orca", "qm-g16"):
        result = runner.invoke(cli, [command, "--help"])
        assert result.exit_code == 0, f"{command} --help failed"
        assert "--force" in result.output, f"{command} is missing --force"


# --------------------------------------------------------------------------- #
# Per-backend and per-config assessments
# --------------------------------------------------------------------------- #
def test_doctor_grades_qm_g16_against_gaussian_config(runner: CliRunner) -> None:
    """``qm-g16`` must not inherit ORCA's memory or job count.

    Regression guard: both QM rows shared ORCA's values, so a generous Gaussian
    setup was reported with ORCA's footprint and vice versa.
    """
    configs = {
        "orca": {"orca": {"maxcore_mb": 32 * 1024, "max_jobs": 8}},
        "gaussian": {"gaussian": {"mem": "256GB", "max_jobs": 1}},
        "docking": {"vina": {"cpu_per_job": 2}},
    }
    for patches in _patch_hardware(total_gb=8.0):
        patches.start()
    try:
        with patch(
            "bimos.shared.user_config.resolve", side_effect=lambda name: (configs[name], {})
        ):
            result = runner.invoke(cli, ["doctor", "--json"])
    finally:
        for patches in _patch_hardware(total_gb=8.0):
            patches.stop()

    assert result.exit_code == 0, result.output
    rows = {p["process"]: p for p in json.loads(result.output)["processes"]}
    # 8 GB of RAM: ORCA at 32 GB x 8 jobs blocks, Gaussian at 256 GB blocks too.
    assert rows["qm-orca"]["level"] == "block"
    assert rows["qm-g16"]["level"] == "block"
    messages = {v["message"] for v in rows["qm-g16"]["checks"]}
    assert any("256 GB" in m for m in messages), messages
    orca_messages = {v["message"] for v in rows["qm-orca"]["checks"]}
    assert any("256 GB" in m for m in orca_messages), orca_messages


def test_screen_guard_honours_the_selected_qm_backend(runner: CliRunner) -> None:
    """``--qm g16`` must be assessed with Gaussian memory, not ORCA's."""
    configs = {
        "docking": {"vina": {"cpu_per_job": 2}},
        "orca": {"orca": {"maxcore_mb": 4 * 1024, "max_jobs": 1}},
        "gaussian": {"gaussian": {"mem": "4096GB", "max_jobs": 1}},
    }

    def invoke(backend: str, protein: str, ligand_dir: str, out: str) -> Result:
        with patch(
            "bimos.shared.user_config.resolve", side_effect=lambda name: (configs[name], {})
        ):
            return runner.invoke(
                cli,
                [
                    "screen",
                    "-p", protein,
                    "--ligands", protein,
                    "--ligand-dir", ligand_dir,
                    "--qm", backend,
                    "-o", out,
                ],
            )

    with tempfile.TemporaryDirectory() as tmp:
        inputs = Path(tmp) / "in"
        inputs.mkdir()
        outputs = Path(tmp) / "out"
        outputs.mkdir()
        protein = str(inputs / "p.pdb")
        ligand_dir = str(inputs / "lig")
        Path(ligand_dir).mkdir()
        Path(protein).write_text("ATOM\n")
        patches = _patch_hardware(total_gb=64.0)
        for p in patches:
            p.start()
        try:
            orca_result = invoke("orca", protein, ligand_dir, str(outputs / "orca"))
            g16_result = invoke("g16", protein, ligand_dir, str(outputs / "g16"))
        finally:
            for p in patches:
                p.stop()

    # ORCA at 4 GB x 1 job fits in 64 GB, so the guard passes it through.
    assert orca_result.exit_code != 1, orca_result.output
    # Gaussian at 4096 GB cannot, so the guard aborts and says why.
    assert g16_result.exit_code == 1, g16_result.output
    assert "4096 GB" in g16_result.output


def test_doctor_json_is_parseable_when_blocked(runner: CliRunner) -> None:
    """``--json`` must emit JSON only, even when processes are not viable."""
    configs = {
        "docking": {"vina": {"cpu_per_job": 2}},
        "orca": {"orca": {"maxcore_mb": 64 * 1024, "max_jobs": 1}},
        "gaussian": {"gaussian": {"mem": "64GB", "max_jobs": 1}},
    }
    patches = _patch_hardware(gpus=[], total_gb=4.0, free_gb=1.0)
    for p in patches:
        p.start()
    try:
        with patch(
            "bimos.shared.user_config.resolve", side_effect=lambda name: (configs[name], {})
        ):
            result = runner.invoke(cli, ["doctor", "--json"])
    finally:
        for p in patches:
            p.stop()

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)  # would raise on any trailing text
    assert payload["viable"] is False
    assert "predict / predict-boltz" in payload["blocked_processes"]


def test_screen_assessment_checks_the_vina_thread_count(runner: CliRunner) -> None:
    """``assess_screen`` used to call ``assess_dock()`` with no config."""
    verdicts = hardware.assess_screen(
        memory_gb=1.0, jobs=1, docking_config={"vina": {"cpu_per_job": 4096}}
    )
    assert any(v.level is hardware.Level.WARN for v in verdicts)
    assert any("4096" in v.message for v in verdicts), [v.message for v in verdicts]
