from typing import Any

import rich_click as click

from bimos.cli.utils import force_option, run_tracked, validate_output
from bimos.prediction.boltz import SUPPORTED_MODELS

PREDICT_EPILOG = """Examples:

\b
  Fold a protein from a FASTA file (GPU required):
  bimos predict sequence.fasta -o ./boltz_out
  Fold from a Boltz YAML input with 3 models:
  bimos predict input.yaml -o ./boltz_out --models 3
  Reproduce an older Boltz-1 run:
  bimos predict sequence.fasta -o ./boltz_out --model boltz1
"""


def model_option(f: Any) -> Any:
    """``--model``/``-m``: pick the Boltz release, overriding ~/.bimos/config."""
    return click.option(
        "--model",
        "-m",
        "model",
        type=click.Choice(SUPPORTED_MODELS),
        default=None,
        help=(
            "Boltz release to run. Defaults to the model in "
            "~/.bimos/config/boltz.yaml (boltz2). Only pass boltz1 to "
            "reproduce results from an older run."
        ),
    )(f)


def _run_boltz(
    input_file: str,
    output: str | None,
    num_models: int,
    background: bool,
    gui: bool,
    kind: str,
    force: bool = False,
    model: str | None = None,
) -> None:
    from bimos.prediction import predict_boltz
    from bimos.shared import hardware

    hardware.guard(kind, hardware.assess_boltz(), force=force)

    validated_output = validate_output(output, [input_file])

    def _run(emit: Any) -> Any:
        return predict_boltz(
            fasta_path=input_file,
            output_dir=validated_output,
            num_models=num_models,
            model=model,
            on_output=emit,
        )

    def _summarize(result: Any) -> None:
        click.echo(f"\nStatus  : {result['status']}")
        click.echo(f"Struct  : {result['struct_file']}")
        click.echo(f"Confidence: {result['confidence']}")

    run_tracked(
        kind=kind,
        meta={"fasta": input_file},
        output=validated_output,
        background=background,
        gui=gui,
        gui_message="Starting prediction and opening dashboard...",
        run_fn=_run,
        summarize=_summarize,
    )


@click.command("predict", epilog=PREDICT_EPILOG)
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory. Defaults to ~/.bimos/workspace/boltz/<name>/ when omitted.")
@click.option("--models", "-n", default=5, show_default=True, help="Number of Boltz models to run.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
@model_option
@force_option
def predict(
    input_file: str,
    output: str | None,
    models: int,
    background: bool,
    gui: bool,
    model: str | None,
    force: bool,
) -> None:
    """Predict protein structure from a FASTA or YAML file using Boltz-2."""
    _run_boltz(
        input_file=input_file,
        output=output,
        num_models=models,
        background=background,
        gui=gui,
        kind="predict",
        force=force,
        model=model,
    )


@click.command("predict-boltz", epilog=PREDICT_EPILOG)
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory. Defaults to ~/.bimos/workspace/boltz/<name>/ when omitted.")
@click.option("--models", "-n", default=5, show_default=True, help="Number of Boltz models to run.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
@model_option
@force_option
def predict_boltz(
    input_file: str,
    output: str | None,
    models: int,
    background: bool,
    gui: bool,
    model: str | None,
    force: bool,
) -> None:
    """Predict protein structure from a YAML or FASTA file using Boltz-2 (alias of 'predict')."""
    _run_boltz(
        input_file=input_file,
        output=output,
        num_models=models,
        background=background,
        gui=gui,
        kind="predict-boltz",
        force=force,
        model=model,
    )
