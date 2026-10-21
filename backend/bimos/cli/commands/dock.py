import os
import tempfile
from pathlib import Path
from typing import Any

import rich_click as click

from bimos.cli.utils import expand_path, force_option, run_tracked, validate_output

DOCK_EPILOG = """Examples:

\b
  Blind screening of a custom SDF set:
  bimos dock receptor.pdb ligands.sdf -o ./docking_out
  Virtual screening with a curated dataset:
  bimos dock receptor.pdb candidates_1000 --dataset
  Targeted docking on a pocket center and size:
  bimos dock receptor.pdb ligands.sdf --center 12.5 3.1 -0.4 --size 20 20 20
  Center the box on a reference ligand pose:
  bimos dock receptor.pdb ligands.sdf --center-on ref_pose.sdf --padding 4
  Center the box on pocket residues:
  bimos dock receptor.pdb ligands.sdf --pocket-residues "A:375,347,351" --size 22 22 22
"""


@click.command("dock", epilog=DOCK_EPILOG)
@click.argument("protein_pdb", type=click.Path(exists=True))
@click.argument("ligands_input", type=str)
@click.option("--dataset", "-d", is_flag=True, help="Treat ligands_input as a curated dataset name (e.g. candidates_1000).")
@click.option("--output", "-o", default=None, help="Output directory. Defaults to ~/.bimos/workspace/docking/<protein>/ when omitted.")
@click.option("--center", nargs=3, type=float, default=None, help="Grid center X Y Z in Angstroms (requires --size).")
@click.option("--size", nargs=3, type=float, default=None, help="Grid size X Y Z in Angstroms (requires --center, --center-on or --pocket-residues).")
@click.option("--center-on", "center_on", type=click.Path(exists=True), default=None, help="Reference ligand SDF (same frame as receptor) to center the grid on.")
@click.option("--pocket-residues", "pocket_residues", default=None, help="Receptor pocket residues, e.g. '375,347,351' or 'A:375-380'.")
@click.option("--padding", type=float, default=None, help="Padding in Angstroms added to reference/pocket span (only with --center-on/--pocket-residues).")
@click.option("--times", type=int, default=None, help="Vina repetitions per ligand.")
@click.option("--exhaustiveness", type=int, default=None, help="Vina exhaustiveness.")
@click.option("--num-modes", "num_modes", type=int, default=None, help="Vina num_modes.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
@force_option
def dock(protein_pdb: str, ligands_input: str, dataset: bool, output: str | None, center: tuple[float, float, float] | None, size: tuple[float, float, float] | None, center_on: str | None, pocket_residues: str | None, padding: float | None, times: int | None, exhaustiveness: int | None, num_modes: int | None, background: bool, gui: bool, force: bool) -> None:
    """Run molecular docking pipeline (Protein PDB + Ligands SDF/Dataset -> best poses)."""
    from bimos.docking import run_docking_pipeline
    from bimos.infrastructure.chembl_db import export_to_sdf, get_available_datasets
    from bimos.shared import hardware
    from bimos.shared.user_config import resolve

    docking_config, _ = resolve("docking")

    ligands_sdf = ligands_input
    if dataset:
        datasets = get_available_datasets()
        if ligands_input not in datasets:
            raise click.ClickException(
                f"Dataset '{ligands_input}' not found. Available: {', '.join(datasets)}"
            )

        # Create a temp SDF for this session
        temp_dir = Path(tempfile.gettempdir()) / "bimos"
        temp_dir.mkdir(parents=True, exist_ok=True)
        ligands_sdf = str(temp_dir / f"{ligands_input}.sdf")
        click.echo(f"Exporting dataset '{ligands_input}' to temporary file...")
        export_to_sdf(ligands_input, Path(ligands_sdf))
    else:
        ligands_sdf = expand_path(ligands_input) or ligands_input
        if not os.path.exists(ligands_sdf):
            raise click.ClickException(f"Ligands file '{ligands_input}' not found.")

    hardware.guard("dock", hardware.assess_dock(docking_config), force=force)

    validated_output = validate_output(output, [protein_pdb, ligands_sdf])
    kwargs = _pipeline_kwargs(center, size, center_on, pocket_residues, padding, times, exhaustiveness, num_modes)

    def _run(emit: Any) -> Any:
        return run_docking_pipeline(
            protein_pdb=protein_pdb,
            ligands_sdf=ligands_sdf,
            output_dir=validated_output,
            on_output=emit,
            **kwargs,
        )

    def _summarize(result: Any) -> None:
        click.echo(f"\nStatus   : {result['status']}")
        click.echo(f"Results  : {result['output_dir']}/results/bests/")

    run_tracked(
        kind="dock",
        meta={"protein": protein_pdb, "ligands": ligands_sdf, "dataset": ligands_input if dataset else None, "center": center, "size": size, "center_on": center_on, "pocket_residues": pocket_residues},
        output=validated_output,
        background=background,
        gui=gui,
        gui_message="Starting docking and opening dashboard...",
        run_fn=_run,
        summarize=_summarize,
    )


def _pipeline_kwargs(center: tuple[float, float, float] | None, size: tuple[float, float, float] | None, center_on: str | None, pocket_residues: str | None, padding: float | None, times: int | None, exhaustiveness: int | None, num_modes: int | None) -> dict[str, object]:
    """Collect non-None CLI options into pipeline kwargs."""
    kwargs: dict[str, object] = {}
    for key, value in (
        ("center", center), ("size", size), ("center_on", center_on),
        ("pocket_residues", pocket_residues), ("padding", padding),
        ("times", times), ("exhaustiveness", exhaustiveness), ("num_modes", num_modes),
    ):
        if value is not None:
            kwargs[key] = value
    return kwargs
