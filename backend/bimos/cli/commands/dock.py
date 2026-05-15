import threading
from pathlib import Path
import rich_click as click
from bimos.infrastructure.job_store import store

@click.command("dock")
@click.argument("protein_pdb", type=click.Path(exists=True))
@click.argument("ligands_input", type=str)
@click.option("--dataset", "-d", is_flag=True, help="Treat ligands_input as a curated dataset name (e.g. candidates_1000).")
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def dock(protein_pdb: str, ligands_input: str, dataset: bool, output: str, background: bool, gui: bool) -> None:
    """Run molecular docking pipeline (Protein PDB + Ligands SDF/Dataset -> best poses)."""
    from bimos.docking import run_docking_pipeline
    from bimos.infrastructure.chembl_db import export_to_sdf, get_available_datasets
    import os
    import tempfile

    ligands_sdf = ligands_input
    if dataset:
        datasets = get_available_datasets()
        if ligands_input not in datasets:
            click.echo(f"Error: Dataset '{ligands_input}' not found. Available: {', '.join(datasets)}", err=True)
            return
        
        # Create a temp SDF for this session
        temp_dir = Path(tempfile.gettempdir()) / "bimos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        ligands_sdf = str(temp_dir / f"{ligands_input}.sdf")
        click.echo(f"Exporting dataset '{ligands_input}' to temporary file...")
        export_to_sdf(ligands_input, Path(ligands_sdf))
    else:
        if not os.path.exists(ligands_sdf):
            click.echo(f"Error: File '{ligands_sdf}' not found.", err=True)
            return

    job = store.create(
        kind="dock",
        meta={"protein": protein_pdb, "ligands": ligands_sdf, "dataset": ligands_input if dataset else None},
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
        import os
        import sys
        click.echo("Running in background. Use 'bimos jobs' to check status.")
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
