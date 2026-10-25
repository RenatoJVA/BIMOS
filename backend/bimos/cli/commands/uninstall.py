"""``bimos uninstall`` — purge every BIMOS-owned residue.

Exit codes: ``0`` success/nothing to do, ``1`` error, ``2`` aborted by a safety
guard or missing confirmation, ``3`` residues still present after the purge or
``--verify``.
"""

import json
import sys
from pathlib import Path

import rich_click as click

from bimos.infrastructure import purge as purge_mod


def _print_human(report: purge_mod.PurgeReport) -> None:
    if report.dry_run:
        click.echo("Dry run: nothing was deleted.\n")
    if report.removed:
        click.echo("Removed:" if not report.dry_run else "Would remove:")
        for item in report.removed:
            click.echo(f"  - {item}")
    if report.skipped:
        click.echo("\nSkipped:")
        for item in report.skipped:
            click.echo(f"  - {item}")
    if report.errors:
        click.echo("\nErrors:", err=True)
        for item in report.errors:
            click.echo(f"  - {item}", err=True)
    if report.remaining:
        click.echo("\nStill present (residues):", err=True)
        for item in report.remaining:
            click.echo(f"  - {item}", err=True)
    elif not report.dry_run and not report.errors:
        click.echo("\nPASS: no BIMOS-owned residue remains.")


def _output(report: purge_mod.PurgeReport, json_output: bool) -> None:
    if json_output:
        click.echo(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        _print_human(report)


@click.command(
    "uninstall",
    epilog="""Examples:

\b
  Preview what would be deleted:
  bimos uninstall --dry-run
  Purge data, web state and container image (keeps the app bundle):
  bimos uninstall --yes
  Purge everything, including the app and build cache:
  bimos uninstall --yes --remove-app --deep
  Prove that nothing is left:
  bimos uninstall --verify
  Keep ~/.bimos (config, workspace, logs):
  bimos uninstall --yes --keep-data
""",
)
@click.option("--dry-run", is_flag=True, help="List what would be removed without deleting anything.")
@click.option("--yes", "-y", is_flag=True, help="Do not ask for confirmation.")
@click.option("--keep-data", is_flag=True, help="Keep ~/.bimos (configuration, workspace, logs).")
@click.option("--deep", is_flag=True, help="Also prune the container build cache (global to the engine).")
@click.option(
    "--remove-app/--no-remove-app",
    default=False,
    help="Also delete BIMOS.app (default: keep the running application bundle).",
)
@click.option("--include-outputs", is_flag=True, help="Also delete job output directories recorded outside ~/.bimos.")
@click.option("--verify", is_flag=True, help="Only verify; exit 3 when BIMOS residues remain.")
@click.option("--print-manifest", is_flag=True, help="Print the static purge manifest as JSON and exit.")
@click.option("--force-path", is_flag=True, help="Allow a custom BIMOS_BASE_PATH without BIMOS markers.")
@click.option("--base-path", type=click.Path(path_type=Path), default=None, help="Override BIMOS_BASE_PATH.")
@click.option("--system", is_flag=True, hidden=True, help="Include system-wide paths (package purge, root only).")
@click.option("--remove-machine", is_flag=True, hidden=True, help="Also remove the Podman machine (destructive).")
@click.option("--json", "json_output", is_flag=True, help="Machine-readable report.")
def uninstall(
    dry_run: bool,
    yes: bool,
    keep_data: bool,
    deep: bool,
    remove_app: bool,
    include_outputs: bool,
    verify: bool,
    print_manifest: bool,
    force_path: bool,
    base_path: Path | None,
    system: bool,
    remove_machine: bool,
    json_output: bool,
) -> None:
    """Remove BIMOS application, data, web state and container image."""
    base = (base_path or purge_mod.default_base_path()).expanduser()

    if print_manifest:
        click.echo(purge_mod.print_manifest())
        return

    if verify:
        report = purge_mod.verify_purge(
            base_path=base,
            include_outputs=include_outputs,
            system=system,
            include_app=remove_app,
        )
        _output(report, json_output)
        sys.exit(0 if not report.remaining else 3)

    if system:
        import os

        if os.name != "nt" and os.geteuid() != 0:
            click.echo("--system requires root (package purge).", err=True)
            sys.exit(2)

    if not dry_run and not yes:
        preview = purge_mod.purge(
            dry_run=True,
            keep_data=keep_data,
            deep=deep,
            remove_app=remove_app,
            include_outputs=include_outputs,
            system=system,
            force_path=force_path,
            remove_machine=remove_machine,
            base_path=base,
        )
        if not json_output:
            click.echo("The following BIMOS-owned items will be removed:\n")
            for item in preview.removed:
                click.echo(f"  - {item.replace(' (would remove)', '')}")
            for item in preview.skipped:
                click.echo(f"  - {item}")
        if not sys.stdin.isatty():
            click.echo("Refusing to purge without confirmation; pass --yes.", err=True)
            sys.exit(2)
        answer = click.prompt(
            "Type PURGE to continue (anything else aborts)", default="", show_default=False
        )
        if answer != "PURGE":
            click.echo("Aborted: nothing was deleted.", err=True)
            sys.exit(2)
        if remove_machine:
            answer = click.prompt(
                "Removing the Podman machine deletes every container/volume in it.\n"
                "Type REMOVE-MACHINE to continue (anything else aborts)",
                default="",
                show_default=False,
            )
            if answer != "REMOVE-MACHINE":
                click.echo("Aborted: nothing was deleted.", err=True)
                sys.exit(2)

    try:
        report = purge_mod.purge(
            dry_run=dry_run,
            keep_data=keep_data,
            deep=deep,
            remove_app=remove_app,
            include_outputs=include_outputs,
            system=system,
            force_path=force_path,
            remove_machine=remove_machine,
            base_path=base,
        )
    except purge_mod.UnsafePathError as exc:
        click.echo(f"Refusing to purge: {exc}", err=True)
        sys.exit(2)

    _output(report, json_output)
    if report.errors:
        sys.exit(1)
    if report.remaining and not dry_run:
        sys.exit(3)
