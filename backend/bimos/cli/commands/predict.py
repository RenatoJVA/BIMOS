import threading
import rich_click as click
from bimos.infrastructure.job_store import store

@click.command("predict")
@click.argument("fasta_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--recycles", default=3, show_default=True, help="ESMFold recycle count.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def predict(fasta_file: str, output: str, recycles: int, background: bool, gui: bool) -> None:
    """Predict protein structure from a FASTA file using ESMFold."""
    from bimos.prediction import predict_structure

    job = store.create(kind="predict", meta={"fasta": fasta_file}, output_dir=output or "")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)

        try:
            result = predict_structure(
                fasta_path=fasta_file,
                output_dir=output,
                num_recycles=recycles,
                on_output=emit,
            )
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                from bimos.cli.utils import get_output_format, output_result
                if get_output_format() != "text":
                    output_result(result)
                else:
                    click.echo(f"\nStatus  : {result['status']}")
                    click.echo(f"PDB     : {result['pdb_file']}")
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


@click.command("predict-boltz")
@click.argument("fasta_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--models", "-n", default=5, show_default=True, help="Number of Boltz models to run.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def predict_boltz(fasta_file: str, output: str, models: int, background: bool, gui: bool) -> None:
    """Predict protein structure from a FASTA file using Boltz-1."""
    from bimos.prediction import predict_boltz

    job = store.create(kind="predict-boltz", meta={"fasta": fasta_file}, output_dir=output or "")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)

        try:
            result = predict_boltz(
                fasta_path=fasta_file,
                output_dir=output,
                num_models=models,
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
        click.echo("Starting Boltz prediction and opening dashboard...")
        start_server(desktop=True)
    elif background:
        from bimos.cli.utils import daemonize
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        daemonize(_run)
    else:
        _run()
