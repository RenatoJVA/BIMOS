"""CLI help contents: every command documents examples and key options."""

import pytest
from click.testing import CliRunner

from bimos.cli.main import cli

COMMANDS_WITH_EXAMPLES = [
    "dock",
    "predict",
    "predict-boltz",
    "workflow",
    "qm-orca",
    "qm-g16",
    "screen",
    "setup",
    "jobs",
    "db",
]


@pytest.mark.parametrize("command", COMMANDS_WITH_EXAMPLES)
def test_help_shows_examples(command: str) -> None:
    result = CliRunner().invoke(cli, [command, "--help"])
    assert result.exit_code == 0, result.output
    assert "Examples" in result.output, f"{command} --help has no Examples section"


def test_dock_help_documents_grid() -> None:
    output = CliRunner().invoke(cli, ["dock", "--help"]).output
    assert "--center" in output
    assert "--pocket-residues" in output
    assert "--center-on" in output


def test_qm_help_mentions_itp_pairs() -> None:
    for command in ("qm-orca", "qm-g16"):
        output = CliRunner().invoke(cli, [command, "--help"]).output
        assert ".itp" in output


def test_workflow_help_documents_batch() -> None:
    output = CliRunner().invoke(cli, ["workflow", "--help"]).output
    assert "--protein-dir" in output
    assert "--ligand-dir" in output


def test_output_help_mentions_default() -> None:
    for command in ("dock", "predict", "workflow"):
        output = CliRunner().invoke(cli, [command, "--help"]).output
        assert ".bimos" in output or "workspace" in output, command


def test_top_help_lists_groups() -> None:
    output = CliRunner().invoke(cli, ["--help"]).output
    assert "dock" in output
    assert "workflow" in output
    assert "qm-orca" in output


def test_doctor_help_explains_the_grades() -> None:
    """The traffic light is the feature; the help has to define it."""
    output = CliRunner().invoke(cli, ["doctor", "--help"]).output
    for token in ("Green", "Yellow", "Red", "--force", "--json"):
        assert token in output, f"doctor --help does not mention {token}"


def test_predict_help_documents_the_model_choice() -> None:
    output = CliRunner().invoke(cli, ["predict", "--help"]).output
    assert "--model" in output
    assert "boltz1" in output and "boltz2" in output


def test_every_pipeline_documents_force() -> None:
    """A guardrail nobody can override from the docs is a support ticket."""
    for command in ("predict", "predict-boltz", "dock", "workflow", "screen", "qm-orca", "qm-g16"):
        output = CliRunner().invoke(cli, [command, "--help"]).output
        assert "--force" in output, f"{command} --help does not document --force"


def test_cli_manual_documents_the_hardware_check() -> None:
    """The packaged manual ships in the wheel; it must not lag the CLI."""
    from pathlib import Path

    import yaml

    manual_path = (
        Path(__file__).resolve().parents[2] / "bimos" / "cli" / "manual.yaml"
    )
    manual = yaml.safe_load(manual_path.read_text(encoding="utf-8"))["manual"]
    text = "\n".join(s.get("content", "") + s["title"] for s in manual["sections"])
    assert "doctor" in text, "bimos/cli/manual.yaml does not mention bimos doctor"
    assert "--force" in text
    assert "Boltz-2" in text, "the manual still presents Boltz-1 as the default"
