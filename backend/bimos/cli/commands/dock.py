import threading
import rich_click as click
from bimos.infrastructure.job_store import store

@click.command("dock")
@click.argument("protein_pdb", type=click.Path(exists=True))
@click.argument("ligands_sdf", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def dock(protein_pdb: str, ligands_sdf: str, output: str, background: bool, gui: bool) -> None:
    """Run molecular docking pipeline (Protein PDB + Ligands SDF -> best poses)."""
    from bimos.core.docking import run_docking_pipeline

    job = store.create(
        kind="dock",
        meta={"protein": protein_pdb, "ligands": ligands_sdf},
        output_dir=output or "",
    )
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)

        try:
            result = run_docking_pipeline(
                protein_pdb=protein_pdb,
                ligands_sdf=ligands_sdf,
                output_dir=output,
                on_output=emit,
            )
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                click.echo(f"\nStatus   : {result['status']}")
                click.echo(f"Results  : {result['output_dir']}/results/bests/")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if gui:
        threading.Thread(target=_run, daemon=True).start()
        from bimos.api.server import start_server
        click.echo("Starting docking and opening dashboard...")
        start_server(desktop=True)
    elif background:
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()
