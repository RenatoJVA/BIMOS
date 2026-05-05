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
            "commands": ["setup", "jobs", "db"],
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
            "commands": ["setup", "jobs", "db"],
        },
    ]
}

from bimos.config.settings import settings
from bimos.infrastructure.job_store import store

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
@click.pass_context
def cli(ctx: click.Context, debug: bool, max: bool, gui: bool, manual: bool, host: str, port: int, headless: bool) -> None:
    """
    Welcome to the **BIMOS** command-line interface.

    You can use this tool to run various molecular biology and chemistry workflows.
    Use `-g` to start the visual desktop interface instead.
    """
    if manual:
        console = Console()
        manual_text = """
# BIMOS CLI Manual

BIMOS (Biomolecular Modeling Suite) is a high-performance toolkit for structural biology and quantum chemistry.
This CLI follows standard POSIX conventions.

## 1. Core Concepts

* **Jobs**: Every calculation (docking, prediction, etc.) is tracked as a job. Use `bimos jobs` to see them.
* **Background Execution**: Most commands block the terminal by default. To run them in the background, use standard Unix `&` or the built-in `-b` flag if available in the command.
* **Desktop UI**: You can start the full GUI at any time using `bimos -g`. 

## 2. Protein Structure Prediction

Predict 3D structures from FASTA files.
* **ESMFold**: `bimos predict sequence.fasta -o output_dir/`
* **Boltz-1**: `bimos predict-boltz sequence.fasta -n 5`

## 3. Molecular Docking & Simulation

* **Docking (Vina)**: `bimos dock protein.pdb ligands.sdf -o results/`
* **MD Simulation (GROMACS)**: `bimos workflow -p protein.pdb --ligand-gro lig.gro --ligand-itp lig.itp`

## 4. Quantum Mechanics

Run charge computations or structure optimizations.
* **Gaussian 16 Pipeline**: `bimos qm-g16 ./ligands_dir -j 4`
* **ORCA Pipeline**: `bimos qm-orca ./ligands_dir -j 4`

## 5. Troubleshooting & Logs

To view detailed logs for a specific background job:
`bimos jobs -l <JOB_ID>`

Enable debug output for any command:
`bimos --debug <COMMAND>`
"""
        console.print(Markdown(manual_text))
        ctx.exit()

    if debug:
        logging.getLogger("bimos").setLevel(logging.DEBUG)
    settings.max_threads = max
    settings.ensure_dirs()

    # GUI Mode Execution
    if gui:
        from bimos.api.server import start_server
        
        if headless:
            click.echo(f"Starting BIMOS headless API on {host}:{port} ...")
        else:
            click.echo(f"Starting BIMOS Desktop UI connected to {host}:{port} ...")

        start_server(host=host, port=port, desktop=not headless)
        ctx.exit()

    # If no subcommand is provided and gui flag was not set, show help
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())
        ctx.exit()


# ── Import and Attach Commands ────────────────────────────────────────────────

from bimos.cli.commands.setup import setup
from bimos.cli.commands.predict import predict, predict_boltz
from bimos.cli.commands.dock import dock
from bimos.cli.commands.workflow import workflow
from bimos.cli.commands.qm import qm_orca, qm_g16
from bimos.cli.commands.system import jobs, db

cli.add_command(setup)
cli.add_command(predict)
cli.add_command(predict_boltz)
cli.add_command(dock)
cli.add_command(workflow)
cli.add_command(qm_orca)
cli.add_command(qm_g16)
cli.add_command(jobs)
cli.add_command(db)
