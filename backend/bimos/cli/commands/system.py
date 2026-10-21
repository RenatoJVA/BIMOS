from pathlib import Path

import rich_click as click

from bimos.infrastructure.job_store import store


@click.group(
    "jobs",
    invoke_without_command=True,
    epilog="""Examples:

\b
  bimos jobs
  bimos jobs -l <JOB_ID>
  bimos jobs kill <JOB_ID>
""",
)
@click.option("--logs", "-l", default=None, help="Show logs for a specific job ID.")
@click.pass_context
def jobs(ctx, logs: str) -> None:  # type: ignore[no-untyped-def]
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


FILTER_OPTS = [
    ("--min-mw", "min_mw", float, "Minimum molecular weight."),
    ("--max-mw", "max_mw", float, "Maximum molecular weight."),
    ("--min-logp", "min_logp", float, "Minimum LogP."),
    ("--max-logp", "max_logp", float, "Maximum LogP."),
    ("--max-hbd", "max_hbd", int, "Max H-bond donors."),
    ("--max-hba", "max_hba", int, "Max H-bond acceptors."),
    ("--max-rotables", "max_rotables", int, "Max rotatable bonds."),
    ("--max-tpsa", "max_tpsa", float, "Max polar surface area."),
    ("--max-lipinski", "max_lipinski", int, "Max Lipinski violations."),
    ("--min-drug-likeness", "min_drug_likeness", float, "Minimum drug-likeness score."),
    ("--min-phase", "min_phase", float, "Minimum development phase (e.g. 4 = approved)."),
    ("--max-aromatic", "max_aromatic", int, "Max aromatic rings."),
]

#: Filters with no PostgreSQL column (SQLite curated datasets only).
SQLITE_ONLY_FILTERS = frozenset(
    {
        "max_hbd",
        "max_hba",
        "max_rotables",
        "max_tpsa",
        "max_lipinski",
        "min_drug_likeness",
        "natural_product",
        "min_phase",
        "max_aromatic",
    }
)


def filter_options(fn):  # type: ignore[no-untyped-def]
    """Attach property-filter flags plus --druglike to a db command."""
    fn = click.option(
        "--druglike", is_flag=True, help="Preset: Lipinski/Veber drug-like bounds (overridable)."
    )(fn)
    fn = click.option("--natural-product", "natural_product", is_flag=True, help="Only natural products.")(fn)
    for flag, name, kind, help_text in FILTER_OPTS:
        fn = click.option(flag, name, type=kind, default=None, help=help_text)(fn)
    return fn


def _collect_filters(druglike: bool, natural_product: bool = False, **kwargs) -> dict:  # type: ignore[no-untyped-def]
    from bimos.infrastructure.chembl_db import normalize_filters

    names = [name for _, name, _, _ in FILTER_OPTS]
    raw = {k: kwargs.get(k) for k in names}
    if natural_product:
        raw["natural_product"] = 1
    try:
        return normalize_filters(raw, druglike=druglike)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from None


@click.group(
    "db",
    epilog="""Examples:

\b
  bimos db list
  bimos db query "acid" --dataset phytocompounds_300
  bimos db query "acid" -d candidates_1000 --druglike --max-mw 450
  bimos db export candidates_1000 ./my_screening_ligands.sdf
  bimos db export candidates_1000 ./druglike.sdf --druglike
""",
)
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
@filter_options
def db_query(query: str, dataset: str, druglike: bool, **filters) -> None:  # type: ignore[no-untyped-def]
    """Search ligands by name or SMILES, optionally filtered by properties."""
    from rich.console import Console
    from rich.table import Table

    console = Console()

    if dataset:
        from bimos.infrastructure.chembl_db import count_candidates, search_candidates

        active = _collect_filters(druglike, **filters)
        total = count_candidates(dataset, query, active)
        candidates = search_candidates(dataset, query, active)
        if not candidates:
            console.print(f"[yellow]No results found in '{dataset}' for '{query}'.[/yellow]")
            return

        suffix = f" [{len(active)} filters]" if active else ""
        table = Table(
            title=f"Virtual Screening Search: {dataset}{suffix} ({total} matches, showing {len(candidates)})",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("ChEMBL ID", style="green")
        table.add_column("MW", justify="right")
        table.add_column("LogP", justify="right")
        table.add_column("DrugLikeness", justify="right")

        for cand in candidates:
            name = str(cand.get("pref_name") or cand.get("chembl_id"))
            mw = f"{cand.get('peso_mol') or 0:.2f}"
            logp = f"{cand.get('alogp') or 0:.2f}"
            dl = f"{cand.get('drug_likeness') or 0:.2f}"
            table.add_row(name[:30], str(cand.get("chembl_id", "")), mw, logp, dl)

        console.print(table)
    else:
        from bimos.infrastructure.database import count_ligands, search_ligands

        active = _collect_filters(druglike, **filters)
        ignored = sorted(set(active) & SQLITE_ONLY_FILTERS)
        if ignored:
            console.print(
                "[yellow]Note: this database has no columns for "
                f"{', '.join(ignored)}; use --dataset for full property filtering.[/yellow]"
            )
        from bimos.infrastructure.database import PropertyBounds

        bounds = PropertyBounds(**{k: active.get(k) for k in ("min_mw", "max_mw", "min_logp", "max_logp")})
        total = count_ligands(query, bounds=bounds)
        ligands = search_ligands(query, limit=50, bounds=bounds)
        if not ligands:
            console.print(f"[yellow]No ligands found matching '{query}'.[/yellow]")
            return

        table = Table(
            title=f"Database Search ({total} matches, showing {len(ligands)})",
            show_header=True,
            header_style="bold magenta",
        )
        table.add_column("Name", style="cyan", no_wrap=True)
        table.add_column("CID", style="green")
        table.add_column("LogP", justify="right")
        table.add_column("MW", justify="right")
        table.add_column("Source", style="dim")

        for lig in ligands:
            table.add_row(
                str(lig.name)[:30],
                str(lig.cid),
                f"{lig.logp or 0:.2f}",
                f"{lig.molar_mass or 0:.2f}",
                str(lig.source),
            )

        console.print(table)


@db.command("export")
@click.argument("dataset")
@click.argument("output", type=click.Path())
@filter_options
def db_export(dataset: str, output: str, druglike: bool, **filters) -> None:  # type: ignore[no-untyped-def]
    """Export a curated dataset to an SDF file for docking (optionally filtered)."""
    from rich.console import Console

    from bimos.infrastructure.chembl_db import export_to_sdf

    console = Console()
    try:
        active = _collect_filters(druglike, **filters)
        out_path = Path(output).resolve()
        if out_path.is_dir():
            out_path = out_path / f"{dataset}.sdf"

        out_path.parent.mkdir(parents=True, exist_ok=True)

        suffix = f" with {len(active)} filters" if active else ""
        console.print(f"Exporting [cyan]{dataset}[/cyan] to [green]{out_path}[/green]{suffix}...")
        count = export_to_sdf(dataset, out_path, active)
        console.print(f"[bold green]✓ Successfully exported {count} compounds.[/bold green]")
    except Exception as e:
        console.print(f"[bold red]Error exporting dataset:[/bold red] {e}")


@click.command("completion")
@click.argument("shell", type=click.Choice(["bash", "zsh", "fish"]))
def completion(shell: str) -> None:
    """Print shell completion script. Source with: eval $(bimos completion bash)"""
    from click.shell_completion import BashComplete, FishComplete, ZshComplete

    from bimos.cli.main import cli

    mapping = {"bash": BashComplete, "zsh": ZshComplete, "fish": FishComplete}
    comp = mapping[shell](cli, ctx_args={}, prog_name="bimos", complete_var="_BIMOS_COMPLETE")
    click.echo(comp.source())
