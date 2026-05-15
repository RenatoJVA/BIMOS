import rich_click as click
from pathlib import Path
from bimos.infrastructure.job_store import store

@click.group("jobs", invoke_without_command=True)
@click.option("--logs", "-l", default=None, help="Show logs for a specific job ID.")
@click.pass_context
def jobs(ctx, logs: str) -> None:
    """List tracked jobs, show logs, or manage jobs."""
    if ctx.invoked_subcommand is not None:
        return

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

@jobs.command("kill")
@click.argument("job_id")
def jobs_kill(job_id: str) -> None:
    """Cancel a running job and kill its containers."""
    if store.cancel(job_id):
        click.echo(f"Job {job_id} canceled.")
    else:
        click.echo(f"Error: Job {job_id} not found.")

@click.group("db")
def db() -> None:
    """Manage the BIMOS ligand database (PostgreSQL and ChEMBL SQLite)."""
    pass

@db.command("init")
def db_init() -> None:
    """Initialize the PostgreSQL schema."""
    from bimos.infrastructure.database import init_db
    click.echo("Initializing database schema...")
    init_db()
    click.echo("Schema initialized.")

@db.command("seed")
def db_seed() -> None:
    """Seed the database with 1000+ ligands."""
    from bimos.infrastructure.database import seed_ligands
    click.echo("Seeding 1000+ ligands...")
    count = seed_ligands()
    click.echo(f"Seeded {count} ligands.")

@db.command("list")
def db_list() -> None:
    """List available curated SQLite datasets for virtual screening."""
    from bimos.infrastructure.chembl_db import get_available_datasets
    datasets = get_available_datasets()
    if not datasets:
        click.echo("No curated datasets found in infrastructure/data/")
        return
    click.echo("Available Virtual Screening Datasets:")
    for ds in datasets:
        click.echo(f" - {ds}")

@db.command("query")
@click.argument("query")
@click.option("--dataset", "-d", default=None, help="Specific SQLite dataset to search in.")
def db_query(query: str, dataset: str) -> None:
    """Search ligands by name or SMILES."""
    from rich.console import Console
    from rich.table import Table
    console = Console()

    if dataset:
        from bimos.infrastructure.chembl_db import search_candidates
        results = search_candidates(dataset, query)
        if not results:
            console.print(f"[yellow]No results found in '{dataset}' for '{query}'.[/yellow]")
            return
        
        table = Table(title=f"Virtual Screening Search: {dataset}", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("ChEMBL ID", style="green")
        table.add_column("MW", justify="right")
        table.add_column("LogP", justify="right")
        table.add_column("DrugLikeness", justify="right")

        for lig in results:
            name = str(lig.get("pref_name") or lig.get("chembl_id"))
            mw = f"{lig.get('peso_mol') or 0:.2f}"
            logp = f"{lig.get('alogp') or 0:.2f}"
            dl = f"{lig.get('drug_likeness') or 0:.2f}"
            table.add_row(name[:30], str(lig.get("chembl_id", "")), mw, logp, dl)
            
        console.print(table)
    else:
        from bimos.infrastructure.database import search_ligands
        results = search_ligands(query)
        if not results:
            console.print(f"[yellow]No ligands found matching '{query}'.[/yellow]")
            return
            
        table = Table(title="Database Search", show_header=True, header_style="bold magenta")
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("CID", style="green")
        table.add_column("LogP", justify="right")
        table.add_column("MW", justify="right")
        table.add_column("Source", style="dim")

        for lig in results:
            table.add_row(
                str(lig.name)[:30], 
                str(lig.cid), 
                f"{lig.logp or 0:.2f}", 
                f"{lig.molar_mass or 0:.2f}", 
                str(lig.source)
            )
            
        console.print(table)

@db.command("export")
@click.argument("dataset")
@click.argument("output", type=click.Path())
def db_export(dataset: str, output: str) -> None:
    """Export a curated dataset to an SDF file for docking."""
    from bimos.infrastructure.chembl_db import export_to_sdf
    from rich.console import Console
    console = Console()
    try:
        out_path = Path(output).resolve()
        if out_path.is_dir():
            out_path = out_path / f"{dataset}.sdf"
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        console.print(f"Exporting [cyan]{dataset}[/cyan] to [green]{out_path}[/green]...")
        count = export_to_sdf(dataset, out_path)
        console.print(f"[bold green]✓ Successfully exported {count} compounds.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error exporting dataset:[/bold red] {e}")
