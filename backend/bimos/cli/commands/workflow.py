from typing import Any

import rich_click as click

from bimos.cli.utils import force_option, run_tracked, validate_output

WORKFLOW_EPILOG = """Examples:

\b
  Apo simulation (protein only):
  bimos workflow -p protein.pdb -o ./md_apo
  Holo simulation (protein + ligand .gro/.itp pair):
  bimos workflow -p protein.pdb --ligand-gro JZ4.gro --ligand-itp JZ4.itp -o ./md_holo
  Batch Holo screening (every protein x ligand pair, outputs Holo-<PROT>-<LIG>/):
  bimos workflow --protein-dir ./Proteins --ligand-dir ./LIG-DIN -o ./md_batch
  Run in background and keep working:
  bimos workflow -p protein.pdb -b
"""


@click.command("workflow", epilog=WORKFLOW_EPILOG)
@click.option("--protein", "-p", "pdb_file", type=click.Path(exists=True), default=None, help="Input protein PDB file (single mode).")
@click.option("--ligand-gro", "ligand_gro", type=click.Path(exists=True), default=None, help="Ligand .gro file (for Holo). The file stem names the output (Holo-<PROT>-<LIG>/); the internal residue name (UNK/LIG/...) drives GROMACS.")
@click.option("--ligand-itp", "ligand_itp", type=click.Path(exists=True), default=None, help="Ligand .itp file (for Holo, must pair with --ligand-gro).")
@click.option("--protein-dir", "protein_dir", type=click.Path(exists=True, file_okay=False), default=None, help="Directory of *.pdb proteins (batch Holo mode: protein x ligand).")
@click.option("--ligand-dir", "ligand_dir", type=click.Path(exists=True, file_okay=False), default=None, help="Directory of *.gro+*.itp ligand pairs matched by stem (batch Holo mode).")
@click.option("--output", "-o", default=None, help="Output directory. Defaults to ~/.bimos/workspace/md/<Apo|Holo>-.../ when omitted.")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
@force_option
def workflow(pdb_file: str | None, ligand_gro: str | None, ligand_itp: str | None, protein_dir: str | None, ligand_dir: str | None, output: str | None, background: bool, gui: bool, force: bool) -> None:
    """Run a GROMACS MD simulation (Prep -> Min -> NVT -> NPT -> SDM -> Analysis)."""
    from bimos.molecular_dynamics import run_md_simulation
    from bimos.shared import hardware

    batch = bool(protein_dir or ligand_dir)
    if batch and not (protein_dir and ligand_dir):
        raise click.ClickException("Batch mode requires both --protein-dir and --ligand-dir.")
    if not batch and not pdb_file:
        raise click.ClickException("Provide --protein for single mode or --protein-dir/--ligand-dir for batch mode.")

    is_holo = bool((ligand_gro and ligand_itp) or batch)
    kind = "workflow-holo-batch" if batch else ("workflow-holo" if is_holo else "workflow-apo")
    inputs = [pdb_file, ligand_gro, ligand_itp] if not batch else [protein_dir, ligand_dir]

    hardware.guard("workflow", hardware.assess_md(), force=force)

    validated_output = validate_output(output, inputs)

    def _run(emit: Any) -> Any:
        if batch:
            return run_md_simulation(
                protein_dir=protein_dir,
                ligand_dir=ligand_dir,
                output_dir=validated_output,
                on_output=emit,
            )
        return run_md_simulation(
            pdb_path=pdb_file,
            ligand_gro=ligand_gro,
            ligand_itp=ligand_itp,
            output_dir=validated_output,
            on_output=emit,
        )

    def _summarize(result: Any) -> None:
        if isinstance(result, list):
            click.echo(f"\nStatus : completed ({len(result)} pairs)")
            for item in result:
                click.echo(f"Results: {item['output_dir']}")
        else:
            click.echo(f"\nStatus : {result['status']}")
            click.echo(f"Results: {result['output_dir']}")

    run_tracked(
        kind=kind,
        meta={"pdb": pdb_file, "gro": ligand_gro, "itp": ligand_itp, "protein_dir": protein_dir, "ligand_dir": ligand_dir},
        output=validated_output,
        background=background,
        gui=gui,
        gui_message=f"Starting {'Holo' if is_holo else 'Apo'} workflow and opening dashboard...",
        run_fn=_run,
        summarize=_summarize,
    )
