"""
# BIMOS CLI

**Biomolecular Modeling Suite** — A modern, high-performance toolkit for structural biology and chemistry.

Use this CLI to run predictions, dockings, and MD simulations locally or submit them as background jobs.
"""

import sys
import logging
import threading
from pathlib import Path

import rich_click as click
import yaml

from rich.console import Console
from rich.markdown import Markdown

# Clig.dev / Rich-Click Configuration
click.rich_click.USE_MARKDOWN = True
click.rich_click.SHOW_ARGUMENTS = True
click.rich_click.GROUP_ARGUMENTS_OPTIONS = True
click.rich_click.STYLE_HELPTEXT = ""
click.rich_click.COMMAND_GROUPS = {
    "bimos": [
        {
            "name": "Protein Structure Prediction",
            "commands": ["predict", "predict-boltz"],
        },
        {
            "name": "Molecular Docking & MD",
            "commands": ["dock", "workflow"],
        },
        {
            "name": "Quantum Mechanics (QM)",
            "commands": ["qm-g16", "qm-orca"],
        },
        {
            "name": "System & Management",
            "commands": ["setup", "jobs", "db", "completion", "key"],
        },
    ],
    "main.py": [
        {
            "name": "Protein Structure Prediction",
            "commands": ["predict", "predict-boltz"],
        },
        {
            "name": "Molecular Docking & MD",
            "commands": ["dock", "workflow"],
        },
        {
            "name": "Quantum Mechanics (QM)",
            "commands": ["qm-g16", "qm-orca"],
        },
        {
            "name": "System & Management",
            "commands": ["setup", "jobs", "db", "completion", "key"],
        },
    ]
}



logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)


def _print(msg: str) -> None:
    click.echo(msg)


# ── Root group ────────────────────────────────────────────────────────────────

@click.group(invoke_without_command=True)
@click.version_option(version="0.1.0", prog_name="bimos")
@click.option("--debug", is_flag=True, default=False, help="Enable debug logging.")
@click.option("--max", is_flag=True, default=False, help="Use all available CPU threads.")
@click.option("-g", "--gui", is_flag=True, default=False, help="Start the BIMOS UI.")
@click.option("-M", "--manual", is_flag=True, default=False, help="Show the comprehensive user manual.")
@click.option("--host", default="127.0.0.1", help="API server host (GUI mode).", hidden=True)
@click.option("--port", default=8000, help="API server port (GUI mode).", hidden=True)
@click.option("--headless", is_flag=True, help="Run GUI in headless mode (GUI mode).", hidden=True)
@click.option("--remote", help="URL of a remote BIMOS server to connect to.", hidden=False)
@click.option("--output-format", "--format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format for results.")
@click.pass_context
def cli(ctx: click.Context, debug: bool, max: bool, gui: bool, manual: bool, host: str, port: int, headless: bool, remote: str, output_format: str) -> None:
    """
    Welcome to the **BIMOS** command-line interface.

    You can use this tool to run various molecular biology and chemistry workflows.
    Use `-g` to start the visual desktop interface instead.
    """
    if manual:
        console = Console()
        manual_path = Path(__file__).parent / "manual.yaml"
        if manual_path.exists():
            with open(manual_path, "r") as f:
                data = yaml.safe_load(f)
            
            m = data.get("manual", {})
            text = f"{m.get('title', '# BIMOS Manual')}\n\n"
            text += f"{m.get('description', '')}\n\n"
            for section in m.get("sections", []):
                text += f"{section.get('title', '## Section')}\n"
                text += f"{section.get('content', '')}\n\n"
            text += f"---\n{m.get('footer', '')}"
            console.print(Markdown(text))
        else:
            console.print(f"[red]Manual file not found at: {manual_path}[/red]")
            console.print("[yellow]Ensure the file was included in the build (check build.py).[/yellow]")
        ctx.exit()

    from bimos.config.settings import settings
    from bimos.infrastructure.job_store import store

    import gc
    gc.collect()

    if debug:
        logging.getLogger("bimos").setLevel(logging.DEBUG)
    settings.max_threads = max
    settings.ensure_dirs()
    from bimos.cli.utils import set_output_format
    set_output_format(output_format)

    # GUI Mode Execution
    if gui:
        from bimos.api.server import start_server
        
        if headless:
            click.echo(f"Starting BIMOS headless API on {host}:{port} ...")
        else:
            target = remote or settings.remote_url
            if target:
                click.echo(f"Connecting BIMOS Desktop UI to remote server: {target} ...")
            else:
                click.echo(f"Starting BIMOS Desktop UI connected to {host}:{port} ...")

        start_server(host=host, port=port, desktop=not headless, remote_url=remote or settings.remote_url)
        ctx.exit()

    _ensure_commands()

    # License check — skip for key, setup, completion, version
    if ctx.invoked_subcommand not in ("key", "setup", "completion", None):
        from bimos.shared.license import is_licensed
        ok, msg = is_licensed()
        if not ok:
            click.echo(f"[ERROR] {msg}")
            ctx.exit(1)

    # If no subcommand is provided and gui flag was not set, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


def _lazy_register_commands() -> None:
    from bimos.cli.commands.setup import setup
    from bimos.cli.commands.predict import predict, predict_boltz
    from bimos.cli.commands.dock import dock
    from bimos.cli.commands.workflow import workflow
    from bimos.cli.commands.qm import qm_orca, qm_g16
    from bimos.cli.commands.system import jobs, db, completion

    cli.add_command(setup)
    cli.add_command(predict)
    cli.add_command(predict_boltz)
    cli.add_command(dock)
    cli.add_command(workflow)
    cli.add_command(qm_orca)
    cli.add_command(qm_g16)
    cli.add_command(jobs)
    cli.add_command(db)
    cli.add_command(completion)

    # License management
    from bimos.cli.commands.license import key as key_cmd
    cli.add_command(key_cmd)


_cli_commands_registered = False


def _ensure_commands() -> None:
    global _cli_commands_registered
    if not _cli_commands_registered:
        _cli_commands_registered = True
        _lazy_register_commands()


_original_resolve = cli.resolve_command
_original_get_help = cli.get_help


def _lazy_resolve(ctx: click.Context, args: list[str]) -> tuple[str | None, click.Command | None, list[str]]:
    _ensure_commands()
    return _original_resolve(ctx, args)


def _lazy_get_help(ctx: click.Context) -> str:
    _ensure_commands()
    return _original_get_help(ctx)


cli.resolve_command = _lazy_resolve  # type: ignore[method-assign]
cli.get_help = _lazy_get_help  # type: ignore[method-assign]

if __name__ == "__main__":
    cli()
