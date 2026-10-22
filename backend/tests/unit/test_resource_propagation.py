"""Regression tests for --max, --jobs and cpu_per_job propagation."""

from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner

from bimos.cli.commands.dock import _pipeline_kwargs
from bimos.cli.main import cli
from bimos.docking.config import DockingConfig
from bimos.docking.pipeline import run_docking_pipeline
from bimos.quantum_chemistry.config import OrcaConfig


def test_docking_max_profile_uses_all_cores(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from bimos.config.settings import settings

    monkeypatch.setattr(settings, "base_path", tmp_path / "base")
    monkeypatch.setattr(settings, "max_threads", True)
    monkeypatch.setattr(settings, "_physical_core_count", staticmethod(lambda: 6))

    cfg = DockingConfig.resolve(max_mode=None)
    assert cfg.profile == "max"
    assert cfg.cpu_per_job == 6


def test_docking_explicit_false_keeps_normal_profile(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from bimos.config.settings import settings

    monkeypatch.setattr(settings, "base_path", tmp_path / "base")
    monkeypatch.setattr(settings, "max_threads", True)

    cfg = DockingConfig.resolve(max_mode=False)
    assert cfg.profile == "default"


def test_qm_explicit_jobs_override_yaml() -> None:
    cfg = OrcaConfig.resolve(max_jobs=7)
    assert cfg.max_jobs == 7


def test_qm_jobs_omitted_uses_yaml_default() -> None:
    cfg = OrcaConfig.resolve(max_jobs=None)
    assert cfg.max_jobs >= 1


def test_run_docking_pipeline_defaults_to_global_max(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    captured: dict[str, Any] = {}

    class FakePipeline:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        def run(self, **kwargs: Any) -> dict[str, Any]:
            captured["run"] = kwargs
            return {"status": "completed"}

    monkeypatch.setattr("bimos.docking.pipeline.DockingPipeline", FakePipeline)
    result = run_docking_pipeline(protein_pdb="p.pdb", ligands_sdf="l.sdf", output_dir=str(tmp_path))

    assert result["status"] == "completed"
    assert captured["max_mode"] is None


def test_dock_cpu_per_job_reaches_pipeline_kwargs() -> None:
    kwargs = _pipeline_kwargs(None, None, None, None, None, None, None, None, 3)
    assert kwargs == {"cpu_per_job": 3}


def test_dock_help_documents_cpu_per_job() -> None:
    result = CliRunner().invoke(cli, ["dock", "--help"])
    assert result.exit_code == 0
    assert "--cpu-per-job" in result.output


def test_screen_help_documents_cpu_per_job() -> None:
    result = CliRunner().invoke(cli, ["screen", "--help"])
    assert result.exit_code == 0
    assert "--cpu-per-job" in result.output
