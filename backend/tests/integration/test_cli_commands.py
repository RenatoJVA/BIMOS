from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from bimos.cli.main import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_cli_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "BIMOS" in result.output


def test_cli_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "0.1.0" in result.output


def test_cli_no_args(runner: CliRunner) -> None:
    result = runner.invoke(cli)
    assert result.exit_code == 0
    assert "predict" in result.output
    assert "dock" in result.output


def test_cli_setup_config_only(runner: CliRunner, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "base_path", tmp_path)
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path / "workspace")
    from bimos.shared import user_config
    monkeypatch.setattr(user_config.settings, "base_path", tmp_path)
    result = runner.invoke(cli, ["setup", "--config-only"])
    assert result.exit_code == 0
    assert "config" in result.output


def test_cli_jobs_empty(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["jobs"])
    assert result.exit_code == 0


def test_cli_jobs_no_logs(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["jobs", "--logs", "nonexistent"])
    assert result.exit_code == 0
    assert "No logs found" in result.output


def test_cli_jobs_kill_not_found(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["jobs", "kill", "nonexistent"])
    assert result.exit_code == 0
    assert "not found" in result.output


def test_cli_db_help(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["db"])
    assert result.exit_code in (0, 2)


def test_cli_predict_missing_fasta(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["predict", "nonexistent.fasta"])
    assert result.exit_code != 0


def test_cli_predict_with_fasta(runner: CliRunner, tmp_path: Path, monkeypatch) -> None:
    fasta = tmp_path / "test.fasta"
    fasta.write_text(">test\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n")
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "cli_test_job"
    fake_store.create.return_value = fake_job
    with patch("bimos.cli.commands.predict.store", fake_store):
        with patch("bimos.prediction.predict_structure", return_value={"status": "completed", "pdb_file": "", "confidence": 0.9, "output_dir": ""}):
            result = runner.invoke(cli, ["predict", str(fasta)])
            assert result.exit_code == 0
            assert "Job ID: cli_test_job" in result.output


def test_cli_dock_missing_file(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["dock", "nonexistent.pdb", "nonexistent.sdf"])
    assert result.exit_code != 0


def test_cli_dock_with_files(runner: CliRunner, tmp_path: Path, sample_receptor: Path) -> None:
    sdf = tmp_path / "ligands.sdf"
    sdf.write_text("lig1\n  test\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n")
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "dock_cli_job"
    fake_store.create.return_value = fake_job
    with patch("bimos.cli.commands.dock.store", fake_store):
        result = runner.invoke(cli, ["dock", str(sample_receptor), str(sdf)])
        assert result.exit_code == 0
        assert "Job ID: dock_cli_job" in result.output


def test_cli_dock_dataset_not_found(runner: CliRunner, tmp_path: Path, sample_receptor: Path) -> None:
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "dock_dataset_job"
    fake_store.create.return_value = fake_job

    with patch("bimos.cli.commands.dock.store", fake_store):
        with patch("bimos.infrastructure.chembl_db.get_available_datasets", return_value=["candidates_1000"]):
            result = runner.invoke(cli, ["dock", str(sample_receptor), "nonexistent_dataset", "--dataset"])
            assert result.exit_code == 0
            assert "not found" in result.output


def test_cli_workflow_missing_pdb(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["workflow", "-p", "nonexistent.pdb"])
    assert result.exit_code != 0


def test_cli_qm_orca_no_directory(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["qm-orca", "nonexistent"])
    assert result.exit_code != 0


def test_cli_qm_g16_no_directory(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["qm-g16", "nonexistent"])
    assert result.exit_code != 0


def test_cli_db_list(runner: CliRunner) -> None:
    with patch("bimos.infrastructure.chembl_db.get_available_datasets", return_value=["candidates_1000", "phytocompounds_300"]):
        result = runner.invoke(cli, ["db", "list"])
        assert result.exit_code == 0
        assert "candidates_1000" in result.output
        assert "phytocompounds_300" in result.output
