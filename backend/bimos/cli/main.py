"""
BIMOS CLI — Primary interface.

Commands:
  setup      Build the bimos/global:latest container image.
  predict    Predict protein structure from FASTA (ESMFold).
  dock       Run molecular docking pipeline (Vina).
  simulate   Run MD simulation (GROMACS).
  qm         Run QM calculation (ORCA).
  qm-orca    Run full ORCA Hirshfeld pipeline on a directory.
  qm-g16     Run full Gaussian Hirshfeld pipeline on a directory.
  jobs       List tracked jobs.
  db         Manage the ligand database.
  gui        Start the BIMOS API server (activates GUI mode).
"""

import sys
import logging
import threading
from pathlib import Path

import click

from bimos.config.settings import settings
from bimos.infrastructure.job_store import store

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)


def _print(msg: str) -> None:
    click.echo(msg)


# ── Root group ────────────────────────────────────────────────────────────────

@click.group()
@click.version_option(version="0.1.0", prog_name="bimos")
@click.option("--debug", is_flag=True, default=False, help="Enable debug logging.")
@click.option("--max", is_flag=True, default=False, help="Use all available CPU threads.")
def cli(debug: bool, max: bool) -> None:
    """BIMOS: Biomolecular Modeling Suite."""
    if debug:
        logging.getLogger("bimos").setLevel(logging.DEBUG)
    settings.max_threads = max
    settings.ensure_dirs()


# ── setup ─────────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--force", is_flag=True, help="Force rebuild even if image exists.")
def setup(force: bool) -> None:
    """Build the bimos/global:latest container image."""
    from bimos.infrastructure.container import build_image, image_exists

    tag = settings.bimos_image
    dockerfile = Path(__file__).parent.parent.parent / "dockers" / "Dockerfile.bimos"

    if not dockerfile.exists():
        click.echo(f"Error: Dockerfile not found at {dockerfile}", err=True)
        sys.exit(1)

    if not force and image_exists(tag):
        click.echo(f"Image {tag} already exists. Use --force to rebuild.")
        return

    context = str(dockerfile.parent.parent)
    click.echo(f"Building {tag}  (this may take 20-40 minutes on first run)...")
    rc = build_image(
        dockerfile=str(dockerfile),
        tag=tag,
        context=context,
        on_output=_print,
    )
    if rc != 0:
        click.echo(f"Build failed with exit code {rc}.", err=True)
        sys.exit(rc)
    click.echo(f"Image {tag} built successfully.")


# ── predict ───────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("fasta_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--recycles", default=3, show_default=True, help="ESMFold recycle count.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def predict(fasta_file: str, output: str, recycles: int, background: bool, gui: bool) -> None:
    """Predict protein structure from a FASTA file using ESMFold."""
    from bimos.core.protein import predict_structure

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
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


@cli.command("predict-boltz")
@click.argument("fasta_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--models", "-n", default=5, show_default=True, help="Number of Boltz models to run.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def predict_boltz(fasta_file: str, output: str, models: int, background: bool, gui: bool) -> None:
    """Predict protein structure from a FASTA file using Boltz-1."""
    from bimos.core.boltz import predict_boltz

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
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


# ── dock ──────────────────────────────────────────────────────────────────────

@cli.command()
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


# ── workflow ──────────────────────────────────────────────────────────────────

@cli.command()
@click.option("--protein", "-p", "pdb_file", type=click.Path(exists=True), required=True, help="Input protein PDB file.")
@click.option("--ligand-gro", "ligand_gro", type=click.Path(exists=True), default=None, help="Ligand .gro file (for Holo).")
@click.option("--ligand-itp", "ligand_itp", type=click.Path(exists=True), default=None, help="Ligand .itp file (for Holo).")
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
def workflow(pdb_file: str, ligand_gro: str, ligand_itp: str, output: str, background: bool, gui: bool) -> None:
    """Run a GROMACS MD simulation (Prep -> Min -> NVT -> NPT -> SDM -> Analysis)."""
    from bimos.core.workflow import run_md_simulation

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
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()



# ── qm ────────────────────────────────────────────────────────────────────────

@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
def qm(input_file: str, output: str, background: bool) -> None:
    """Run a single QM calculation using ORCA (host binary)."""
    from bimos.core.workflow import run_qm_calculation

    job = store.create(kind="qm", meta={"input": input_file}, output_dir=output or "")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)

        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background:
                click.echo(line)

        try:
            result = run_qm_calculation(
                input_file=input_file,
                output_dir=output,
                on_output=emit,
            )
            store.complete(job.id, exit_code=0)
            if not background:
                click.echo(f"\nStatus: {result['status']}")
                click.echo(f"Output: {result['output_file']}")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if background:
        click.echo("Running in background. Use 'bimos jobs' to check status.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


@cli.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output directory.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
def gaussian(input_file: str, output: str, background: bool) -> None:
    """Run a single QM calculation using Gaussian (host binary)."""
    from bimos.core.workflow import run_gaussian_calculation

    job = store.create(kind="gaussian", meta={"input": input_file}, output_dir=output or "")
    click.echo(f"Job ID: {job.id}")

    def _run() -> None:
        store.start(job.id)
        def emit(line: str) -> None:
            store.log(job.id, line)
            if not background:
                click.echo(line)
        try:
            result = run_gaussian_calculation(input_file=input_file, output_dir=output, on_output=emit)
            store.complete(job.id, exit_code=0)
            if not background:
                click.echo(f"\nStatus: {result['status']}")
                click.echo(f"Output dir: {result['output_dir']}")
        except Exception as exc:
            store.fail(job.id, str(exc))
            click.echo(f"Error: {exc}", err=True)

    if background:
        click.echo("Running in background.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


@cli.command("qm-orca")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--jobs", "-j", default=2, help="Max parallel jobs.")
@click.option("--charge", "-q", default=0, help="Total charge.")
@click.option("--background", "-b", is_flag=True, help="Run in background.")
@click.option("--gui", "-g", is_flag=True, help="Open GUI dashboard.")
def qm_orca(directory: str, jobs: int, charge: int, background: bool, gui: bool) -> None:
    """Run full ORCA Hirshfeld pipeline on a directory of .gro files."""
    from bimos.core.qm import run_orca_pipeline

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
        click.echo("Running in background.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


@cli.command("qm-g16")
@click.argument("directory", type=click.Path(exists=True))
@click.option("--jobs", "-j", default=2, help="Max parallel jobs.")
@click.option("--charge", "-q", default=0, help="Total charge.")
@click.option("--background", "-b", is_flag=True, help="Run in background.")
@click.option("--gui", "-g", is_flag=True, help="Open GUI dashboard.")
def qm_g16(directory: str, jobs: int, charge: int, background: bool, gui: bool) -> None:
    """Run full Gaussian Hirshfeld pipeline on a directory of .gro files."""
    from bimos.core.qm import run_gaussian_pipeline

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
        click.echo("Running in background.")
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


# ── jobs ──────────────────────────────────────────────────────────────────────

@cli.command("jobs")
@click.option("--logs", "-l", default=None, help="Show logs for a specific job ID.")
def jobs(logs: str) -> None:
    """List all tracked jobs or show logs for a specific job."""
    if logs:
        lines = store.get_logs(logs)
        if not lines:
            click.echo(f"No logs found for job {logs}.")
        for line in lines:
            click.echo(line)
        return

    all_jobs = store.list_all()
    if not all_jobs:
        click.echo("No jobs recorded in this session.")
        return

    header = f"{'ID':<14} {'KIND':<10} {'STATUS':<12} {'CREATED':>30}"
    click.echo(header)
    click.echo("-" * len(header))
    for j in all_jobs:
        click.echo(f"{j.id:<14} {j.kind:<10} {j.status:<12} {j.created_at:>30}")


# ── db ────────────────────────────────────────────────────────────────────────

@cli.command("db")
@click.option("--init", is_flag=True, help="Initialize the PostgreSQL schema.")
@click.option("--seed", is_flag=True, help="Seed the database with 1000+ ligands.")
@click.option("--query", default=None, help="Search ligands by name or SMILES substring.")
def db(init: bool, seed: bool, query: str) -> None:
    """Manage the BIMOS ligand database."""
    from bimos.infrastructure.database import init_db, seed_ligands, search_ligands

    if init:
        click.echo("Initializing database schema...")
        init_db()
        click.echo("Schema initialized.")

    if seed:
        click.echo("Seeding 1000+ ligands...")
        count = seed_ligands()
        click.echo(f"Seeded {count} ligands.")

    if query:
        results = search_ligands(query)
        if not results:
            click.echo(f"No ligands found matching '{query}'.")
            return
        click.echo(f"{'Name':<30} {'CID':<15} {'LogP':>6} {'MW':>10} {'Source':<25}")
        click.echo("-" * 90)
        for lig in results:
            click.echo(
                f"{lig.name:<30} {lig.cid:<15} {lig.logp or 0:>6.2f} "
                f"{lig.molar_mass or 0:>10.2f} {lig.source:<25}"
            )


# ── gui ───────────────────────────────────────────────────────────────────────

@cli.command("gui")
@click.option("--port", default=8000, show_default=True, help="API server port.")
@click.option("--host", default="127.0.0.1", show_default=True, help="API server host.")
@click.option("--no-desktop", is_flag=True, help="Do not open the desktop window (run headless server only).")
def gui(port: int, host: str, no_desktop: bool) -> None:
    """Start the BIMOS API server and open the native desktop UI."""
    from bimos.api.server import start_server

    if not no_desktop:
        click.echo(f"Starting BIMOS Desktop UI connected to {host}:{port} ...")
    else:
        click.echo(f"Starting BIMOS headless API on {host}:{port} ...")

    start_server(host=host, port=port, desktop=not no_desktop)
