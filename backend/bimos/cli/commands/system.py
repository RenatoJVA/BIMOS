import rich_click as click
from bimos.infrastructure.job_store import store

@click.command("jobs")
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

@click.command("db")
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
