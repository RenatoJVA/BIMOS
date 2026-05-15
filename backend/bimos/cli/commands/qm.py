import threading
import rich_click as click
from bimos.infrastructure.job_store import store

@click.command("qm-orca")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--jobs", "-j", default=2, help="Max parallel jobs.")
@click.option("--charge", "-q", default=0, help="Total charge.")
@click.option("--background", "-b", is_flag=True, help="Run in background.")
@click.option("--gui", "-g", is_flag=True, help="Open GUI dashboard.")
def qm_orca(directory: str, jobs: int, charge: int, background: bool, gui: bool) -> None:
    """Run full ORCA Hirshfeld pipeline on a directory of .gro files."""
    from bimos.quantum_chemistry import run_orca_pipeline

    job = store.create(kind="qm-orca", meta={"dir": directory}, output_dir="")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)
        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)
        try:
            result = run_orca_pipeline(directory, max_jobs=jobs, charge=charge, on_output=emit)
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                click.echo(f"\nStatus: {result['status']}")
                click.echo(f"Updated {len(result['results'])} ITP files.")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if gui:
        threading.Thread(target=_run, daemon=True).start()
        from bimos.api.server import start_server
        click.echo("Starting ORCA pipeline and opening dashboard...")
        start_server(desktop=True)
    elif background:
        import os
        import sys
        click.echo("Running in background.")
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        with open(os.devnull, 'r') as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open(os.devnull, 'a+') as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
        _run()
    else:
        _run()

@click.command("qm-g16")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--jobs", "-j", default=2, help="Max parallel jobs.")
@click.option("--charge", "-q", default=0, help="Total charge.")
@click.option("--background", "-b", is_flag=True, help="Run in background.")
@click.option("--gui", "-g", is_flag=True, help="Open GUI dashboard.")
def qm_g16(directory: str, jobs: int, charge: int, background: bool, gui: bool) -> None:
    """Run full Gaussian Hirshfeld pipeline on a directory of .gro files."""
    from bimos.quantum_chemistry import run_gaussian_pipeline

    job = store.create(kind="qm-g16", meta={"dir": directory}, output_dir="")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)
        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)
        try:
            result = run_gaussian_pipeline(directory, max_jobs=jobs, charge=charge, on_output=emit)
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                click.echo(f"\nStatus: {result['status']}")
                click.echo(f"Updated {len(result['results'])} ITP files.")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if gui:
        threading.Thread(target=_run, daemon=True).start()
        from bimos.api.server import start_server
        click.echo("Starting Gaussian pipeline and opening dashboard...")
        start_server(desktop=True)
    elif background:
        import os
        import sys
        click.echo("Running in background.")
        if os.fork() > 0:
            sys.exit(0)
        os.setsid()
        if os.fork() > 0:
            sys.exit(0)
        with open(os.devnull, 'r') as f:
            os.dup2(f.fileno(), sys.stdin.fileno())
        with open(os.devnull, 'a+') as f:
            os.dup2(f.fileno(), sys.stdout.fileno())
            os.dup2(f.fileno(), sys.stderr.fileno())
        _run()
    else:
        _run()
