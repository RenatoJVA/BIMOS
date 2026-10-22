from typing import Any

import rich_click as click

from bimos.cli.utils import force_option, run_tracked, validate_output

SCREEN_EPILOG = """Examples:

\b
  Full cascade (APO -> docking -> QM -> top-1 HOLO + report):
  bimos screen -p protein.pdb --ligands ligands.sdf --ligand-dir ./LIG-DIN -o ./screen_out
  Skip APO with an already equilibrated protein:
  bimos screen --protein-eq protein_eq.pdb --ligands ligands.sdf --ligand-dir ./LIG-DIN
  Screen a curated dataset with a targeted box and Gaussian charges:
  bimos screen -p protein.pdb --dataset candidates_1000 --ligand-dir ./LIG-DIN \\
      --pocket-residues "A:375,347,351" --qm g16 --min-score -7.0

The ligand library (--ligand-dir) must hold .gro + .itp pairs sharing the
SDF candidate stems (e.g. JZ4.sdf plus JZ4.gro/JZ4.itp). The top-N hits by
Vina energy with a complete pair each run QM + full HOLO
(1 APO + 1 docking + N x (QM + HOLO)); progress persists in screen.json,
so re-running resumes after the last completed hit. A failed hit is marked
and skipped; the cascade aborts only if every hit fails.
"""


@click.command("screen", epilog=SCREEN_EPILOG)
@click.option(
    "--protein",
    "-p",
    "protein",
    type=click.Path(exists=True),
    default=None,
    help="Input protein PDB file (APO runs first).",
)
@click.option(
    "--protein-eq",
    "protein_eq",
    type=click.Path(exists=True),
    default=None,
    help="Already equilibrated protein PDB (skips APO).",
)
@click.option(
    "--ligands", "ligands_sdf", type=click.Path(exists=True), default=None, help="Ligands SDF for docking."
)
@click.option(
    "--dataset", default=None, help="Curated dataset name instead of --ligands (e.g. candidates_1000)."
)
@click.option(
    "--ligand-dir",
    "ligand_dir",
    type=click.Path(exists=True, file_okay=False),
    required=True,
    help="Directory of parametrized .gro+.itp pairs matched by candidate stem.",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output directory. Defaults to ~/.bimos/workspace/screen/ when omitted.",
)
@click.option(
    "--qm",
    "qm_backend",
    type=click.Choice(["orca", "g16"]),
    default="orca",
    show_default=True,
    help="QM backend for charge refinement.",
)
@click.option("--charge", "-q", default=0, help="Integer net charge of the selected ligands.")
@click.option("--jobs", "-j", type=click.IntRange(min=1), default=None, help="Max parallel QM calculations (defaults to the YAML/MAX profile).")
@click.option(
    "--top-n",
    "top_n",
    type=click.IntRange(min=1),
    default=5,
    show_default=True,
    help="How many top-ranked hits run QM + full HOLO each.",
)
@click.option(
    "--min-score",
    "min_score",
    type=float,
    default=None,
    help="Vina score cutoff (kcal/mol): hits above it are skipped.",
)
@click.option(
    "--center", nargs=3, type=float, default=None, help="Docking grid center X Y Z (requires --size)."
)
@click.option("--size", nargs=3, type=float, default=None, help="Docking grid size X Y Z.")
@click.option(
    "--center-on",
    "center_on",
    type=click.Path(exists=True),
    default=None,
    help="Reference ligand SDF to center the docking grid on.",
)
@click.option(
    "--pocket-residues", "pocket_residues", default=None, help="Docking pocket residues, e.g. '375,347,351'."
)
@click.option("--padding", type=float, default=None, help="Padding for reference/pocket-derived boxes.")
@click.option("--times", type=int, default=None, help="Vina repetitions per ligand.")
@click.option("--cpu-per-job", "cpu_per_job", type=click.IntRange(min=1), default=None, help="Vina CPU threads per ligand (defaults to config/--max).")
@click.option("--background", "-b", is_flag=True, help="Run in background thread.")
@click.option("--gui", "-g", is_flag=True, help="Open the GUI dashboard for monitoring.")
@force_option
def screen(
    protein: str | None,
    protein_eq: str | None,
    ligands_sdf: str | None,
    dataset: str | None,
    ligand_dir: str,
    output: str | None,
    qm_backend: str,
    charge: int,
    jobs: int | None,
    top_n: int,
    min_score: float | None,
    center: tuple[float, float, float] | None,
    size: tuple[float, float, float] | None,
    center_on: str | None,
    pocket_residues: str | None,
    padding: float | None,
    times: int | None,
    cpu_per_job: int | None,
    background: bool,
    gui: bool,
    force: bool,
) -> None:
    """Run the full screening cascade (APO -> Docking -> QM -> top-N HOLO + report)."""
    from bimos.screening import run_screen
    from bimos.shared import hardware

    if (protein is None) == (protein_eq is None):
        raise click.ClickException("Provide --protein or --protein-eq (mutually exclusive).")
    if (ligands_sdf is None) == (dataset is None):
        raise click.ClickException("Provide --ligands or --dataset (mutually exclusive).")

    validated_output = validate_output(output, [protein or protein_eq, ligands_sdf, ligand_dir])
    kwargs: dict[str, Any] = {
        "qm_backend": qm_backend,
        "charge": charge,
        "max_jobs": jobs,
        "top_n": top_n,
    }
    if min_score is not None:
        kwargs["min_score"] = min_score
    for key, value in (
        ("center", center),
        ("size", size),
        ("center_on", center_on),
        ("pocket_residues", pocket_residues),
        ("padding", padding),
        ("times", times),
        ("cpu_per_job", cpu_per_job),
    ):
        if value is not None:
            kwargs[key] = value

    from bimos.cli.commands.qm import _effective_qm_jobs, _qm_memory_gb
    from bimos.shared.user_config import resolve

    # The QM stage runs with the selected backend, so assess that one: ORCA and
    # Gaussian are configured with different per-job memory.
    qm_config_name = {"orca": "orca", "g16": "gaussian"}.get(qm_backend)
    if qm_config_name is None:
        raise click.ClickException(f"Unknown QM backend {qm_backend!r}.")

    try:
        docking_config, _ = resolve("docking")
    except (OSError, ValueError, KeyError):
        docking_config = None

    hardware.guard(
        "screen",
        hardware.assess_screen(
            _qm_memory_gb(qm_config_name),
            _effective_qm_jobs(qm_config_name, jobs),
            docking_config=docking_config,
        ),
        force=force,
    )

    def _run(emit: Any) -> Any:
        return run_screen(
            protein=protein,
            protein_eq=protein_eq,
            ligands_sdf=ligands_sdf,
            dataset=dataset,
            ligand_dir=ligand_dir,
            output_dir=validated_output,
            on_output=emit,
            **kwargs,
        )

    def _summarize(result: Any) -> None:
        click.echo(f"\nStatus   : {result['status']}")
        header = f"{'CANDIDATE':<16} {'VINA':>10}  HOLO"
        click.echo(header)
        for candidate, score, holo in zip(
            result["candidates"], result["vina_scores"], result["holo_dirs"], strict=True
        ):
            click.echo(f"{candidate:<16} {score:>10.3f}  {holo or '(failed)'}")
        click.echo(f"Report   : {result['report']}")

    run_tracked(
        kind="screen",
        meta={
            "protein": protein or protein_eq,
            "dataset": dataset,
            "ligand_dir": ligand_dir,
            "qm": qm_backend,
            "top_n": top_n,
        },
        output=validated_output,
        background=background,
        gui=gui,
        gui_message="Starting screening cascade and opening dashboard...",
        run_fn=_run,
        summarize=_summarize,
    )
