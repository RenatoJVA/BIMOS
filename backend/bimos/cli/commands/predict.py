import threading
import rich_click as click
from bimos.infrastructure.job_store import store

def _run_boltz(
    input_file: str,
    output: str,
    num_models: int,
    background: bool,
    gui: bool,
    kind: str,
) -> None:
    from bimos.prediction import predict_boltz

    job = store.create(kind=kind, meta={"fasta": input_file}, output_dir=output or "")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)

        try:
            result = predict_boltz(
                fasta_path=input_file,
                output_dir=output,
                num_models=num_models,
                on_output=emit,
            )
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                from bimos.cli.utils import get_output_format, output_result
                if get_output_format() != "text":
                    output_result(result)
                else:
                    click.echo(f"\nStatus  : {result['status']}")
                    click.echo(f"Struct  : {result['struct_file']}")
                    click.echo(f"Confidence: {result['confidence']}")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if gui:
        threading.Thread(target=_run, daemon=True).start()
        from bimos.api.server import start_server
        click.echo("Starting prediction and opening dashboard...")
        start_server(desktop=True)
    elif background:
        from bimos.cli.utils import daemonize
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        daemonize(_run)
    else:
        _run()


@click.command("predict")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--models", "-n", default=5, show_default=True, help="Number of Boltz models to run.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def predict(input_file: str, output: str, models: int, background: bool, gui: bool) -> None:
    """Predict protein structure from a FASTA or YAML file using Boltz-1."""
    _run_boltz(
        input_file=input_file,
        output=output,
        num_models=models,
        background=background,
        gui=gui,
        kind="predict",
    )


@click.command("predict-boltz")
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--models", "-n", default=5, show_default=True, help="Number of Boltz models to run.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def predict_boltz(input_file: str, output: str, models: int, background: bool, gui: bool) -> None:
    """Predict protein structure from a YAML or FASTA file using Boltz-1 (alias of 'predict')."""
    _run_boltz(
        input_file=input_file,
        output=output,
        num_models=models,
        background=background,
        gui=gui,
        kind="predict-boltz",
    )
