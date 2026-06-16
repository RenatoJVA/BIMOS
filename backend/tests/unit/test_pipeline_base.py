import logging
from pathlib import Path
from typing import Any

import pytest

from bimos.shared.pipeline import Pipeline


class ConcretePipeline(Pipeline):
    workspace_subdir = "test_jobs"

    def run(self, **kwargs: Any) -> dict[str, Any]:
        return {"status": "completed", "output_dir": str(self.output_dir)}


def test_pipeline_creates_output_dir(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    pipeline = ConcretePipeline(output_dir=str(output_dir))
    assert output_dir.exists()
    assert pipeline.output_dir == output_dir


def test_pipeline_default_output_dir(tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    monkeypatch.setattr("bimos.config.settings.settings.workspace_path", tmp_path)
    pipeline = ConcretePipeline()
    expected = tmp_path / "test_jobs"
    assert pipeline.output_dir == expected


def test_pipeline_logging(caplog, tmp_path: Path) -> None:
    lines: list[str] = []

    def capture(msg: str) -> None:
        lines.append(msg)

    pipeline = ConcretePipeline(output_dir=str(tmp_path), on_output=capture)
    caplog.set_level(logging.INFO)
    pipeline.log("Test message")
    assert "Test message" in caplog.text
    assert "Test message" in lines


def test_pipeline_log_without_callback(caplog, tmp_path: Path) -> None:
    pipeline = ConcretePipeline(output_dir=str(tmp_path))
    caplog.set_level(logging.INFO)
    pipeline.log("No callback")
    assert "No callback" in caplog.text


def test_pipeline_abstract_cannot_be_instantiated() -> None:
    with pytest.raises(TypeError):
        Pipeline()  # type: ignore[abstract]


def test_pipeline_run_returns_dict(tmp_path: Path) -> None:
    pipeline = ConcretePipeline(output_dir=str(tmp_path))
    result = pipeline.run()
    assert isinstance(result, dict)
    assert result["status"] == "completed"


def test_pipeline_inherits_workspace_subdir() -> None:
    assert ConcretePipeline.workspace_subdir == "test_jobs"


def test_pipeline_with_string_output_dir(tmp_path: Path) -> None:
    d = str(tmp_path / "string_output")
    pipeline = ConcretePipeline(output_dir=d)
    assert Path(d).exists()
