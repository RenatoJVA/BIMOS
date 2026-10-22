"""CLI path handling: exit codes, output validation, formats (no containers)."""

from pathlib import Path
from typing import Any

import click
import pytest
from click.testing import CliRunner

from bimos.cli import utils
from bimos.cli.main import cli
from bimos.cli.utils import output_result, run_tracked, validate_output


@pytest.fixture
def pdb_file(tmp_path: Path) -> Path:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text(
        "ATOM      1  N   MET A   1      12.234   9.679   8.022  1.00  0.00           N\nEND\n"
    )
    return pdb


def test_dock_unknown_dataset_fails(pdb_file: Path) -> None:
    result = CliRunner().invoke(cli, ["dock", str(pdb_file), "nope", "--dataset"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_dock_missing_file_fails(pdb_file: Path) -> None:
    result = CliRunner().invoke(cli, ["dock", str(pdb_file), "missing.sdf"])
    assert result.exit_code != 0
    assert "not found" in result.output


def test_workflow_batch_needs_both_dirs(tmp_path: Path) -> None:
    result = CliRunner().invoke(cli, ["workflow", "--protein-dir", str(tmp_path)])
    assert result.exit_code != 0
    assert "protein-dir" in result.output


def test_workflow_needs_protein_or_batch() -> None:
    result = CliRunner().invoke(cli, ["workflow"])
    assert result.exit_code != 0


def test_qm_rejects_file_as_directory(tmp_path: Path) -> None:
    target = tmp_path / "lig.gro"
    target.write_text("x\n")
    result = CliRunner().invoke(cli, ["qm-orca", str(target)])
    assert result.exit_code != 0


def test_validate_output_rejects_existing_file(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x")
    with pytest.raises(Exception, match="not a directory"):
        validate_output(str(target), [])


def test_validate_output_rejects_inside_input(tmp_path: Path) -> None:
    inputs = tmp_path / "inputs"
    inputs.mkdir()
    with pytest.raises(Exception, match="must not be inside"):
        validate_output(str(inputs / "out"), [str(inputs)])


def test_validate_output_expands_tilde(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    assert validate_output("~/out", []) == str(tmp_path / "out")


def test_validate_output_none_passthrough() -> None:
    assert validate_output(None, []) is None


class _FakeStore:
    def __init__(self) -> None:
        self.events: list[str] = []

    def create(self, **kwargs: Any) -> Any:
        self.events.append("create")

        class _Job:
            id = "job123"

        return _Job()

    def start(self, job_id: str) -> None:
        self.events.append("start")

    def get(self, job_id: str) -> None:
        return None

    def log(self, job_id: str, line: str) -> None:
        self.events.append("log")

    def complete(self, job_id: str, exit_code: int = 0) -> None:
        self.events.append("complete")

    def fail(self, job_id: str, error: str) -> None:
        self.events.append("fail")

    def cancel(self, job_id: str) -> bool:
        self.events.append("cancel")
        return True


def test_run_tracked_foreground_lifecycle(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeStore()
    monkeypatch.setattr("bimos.infrastructure.job_store.store", fake)
    seen: list[str] = []

    def _run(emit: Any) -> dict[str, Any]:
        emit("hello")
        return {"status": "completed"}

    run_tracked(
        kind="dock", meta={}, output=None, background=False, gui=False,
        gui_message="", run_fn=_run, summarize=lambda r: seen.append(r["status"]),
    )
    assert fake.events == ["create", "start", "log", "complete"]
    assert seen == ["completed"]


def test_run_tracked_failure_marks_job(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeStore()
    monkeypatch.setattr("bimos.infrastructure.job_store.store", fake)

    def _run(emit: Any) -> dict[str, Any]:
        raise RuntimeError("boom")

    with pytest.raises(click.exceptions.Exit) as exc_info:
        run_tracked(
            kind="dock", meta={}, output=None, background=False, gui=False,
            gui_message="", run_fn=_run, summarize=lambda r: None,
        )
    assert exc_info.value.exit_code == 1
    assert fake.events == ["create", "start", "fail"]


def test_run_tracked_cancellation_marks_job(monkeypatch: pytest.MonkeyPatch) -> None:
    from bimos.infrastructure import cancellation

    fake = _FakeStore()
    monkeypatch.setattr("bimos.infrastructure.job_store.store", fake)

    def _run(emit: Any) -> dict[str, Any]:
        cancellation.request("job123")
        return {"status": "completed"}

    with pytest.raises(click.exceptions.Exit) as exc_info:
        run_tracked(
            kind="dock", meta={}, output=None, background=False, gui=False,
            gui_message="", run_fn=_run, summarize=lambda r: None,
        )
    assert exc_info.value.exit_code == 1
    assert fake.events == ["create", "start", "cancel"]


@pytest.fixture
def text_format() -> Any:
    previous = utils.get_output_format()
    yield
    utils.set_output_format(previous)


def test_output_result_accepts_list(text_format: Any, capsys: Any) -> None:
    utils.set_output_format("json")
    output_result([{"status": "completed", "output_dir": "/tmp/x"}])
    assert "completed" in capsys.readouterr().out
    utils.set_output_format("csv")
    output_result([{"status": "completed", "output_dir": "/tmp/x"}])
    out = capsys.readouterr().out
    assert "status" in out and "completed" in out
