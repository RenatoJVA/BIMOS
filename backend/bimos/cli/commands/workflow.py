import threading
import rich_click as click
from bimos.infrastructure.job_store import store

@click.command("workflow")
@click.option("--protein", "-p", "pdb_file", type=click.Path(exists=True), required=True, help="Input protein PDB file.")
@click.option("--ligand-gro", "ligand_gro", type=click.Path(exists=True), default=None, help="Ligand .gro file (for Holo).")
@click.option("--ligand-itp", "ligand_itp", type=click.Path(exists=True), default=None, help="Ligand .itp file (for Holo).")
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def workflow(pdb_file: str, ligand_gro: str, ligand_itp: str, output: str, background: bool, gui: bool) -> None:
    """Run a GROMACS MD simulation (Prep -> Min -> NVT -> NPT -> SDM -> Analysis)."""
    from bimos.molecular_dynamics import run_md_simulation

    is_holo = bool(ligand_gro and ligand_itp)
    kind = "workflow-holo" if is_holo else "workflow-apo"
    
    job = store.create(
        kind=kind, 
        meta={"pdb": pdb_file, "gro": ligand_gro, "itp": ligand_itp}, 
        output_dir=output or ""
    )
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background and not gui:
                click.echo(line)

        try:
            result = run_md_simulation(
                pdb_path=pdb_file,
                ligand_gro=ligand_gro,
                ligand_itp=ligand_itp,
                output_dir=output,
                on_output=emit,
            )
            store.complete(job.id, exit_code=0)
            if not background and not gui:
                from bimos.cli.utils import get_output_format, output_result
                if get_output_format() != "text":
                    output_result(result)
                else:
                    click.echo(f"\nStatus : {result['status']}")
                    click.echo(f"Results: {result['output_dir']}")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if gui:
        threading.Thread(target=_run, daemon=True).start()
        from bimos.api.server import start_server
        click.echo(f"Starting {'Holo' if is_holo else 'Apo'} workflow and opening dashboard...")
        start_server(desktop=True)
    elif background:
        from bimos.cli.utils import daemonize
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        daemonize(_run)
    else:
        _run()
