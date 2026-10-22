import shutil
from pathlib import Path
from typing import Any

import rich_click as click

from bimos.cli.utils import force_option, run_tracked

QM_EPILOG = """Examples:

\b
  Refine charges of every ligand in a directory with ORCA:
  bimos qm-orca ./ligands -j 4 --charge 0
  Same with Gaussian 16 and a +1 net charge:
  bimos qm-g16 ./ligands -j 4 --charge 1

The directory must contain matching .gro + .itp pairs per ligand
(e.g. JZ4.gro + JZ4.itp). Outputs are written next to the inputs
as <name>-hirsh.itp. Requires the QM binary on the host
(ORCA_PATH / GAUSSIAN_PATH in ~/.bimos/.env) plus OpenBabel (obabel).
"""


def _require_qm_toolchain(kind: str) -> None:
    """Fail fast with a clear message when the host QM toolchain is missing."""
    from bimos.config.settings import settings

    if kind == "orca":
        binary, var, name = settings.orca_path, "ORCA_PATH", "ORCA"
    else:
        binary, var, name = settings.gaussian_path, "GAUSSIAN_PATH", "Gaussian 16"
    if not binary or not Path(binary).exists():
        raise click.ClickException(
            f"{name} binary not found (checked {var}={binary or 'unset'}). "
            f"Install {name} on this host and set {var} in ~/.bimos/.env."
        )
    if shutil.which("obabel") is None:
        raise click.ClickException(
            "OpenBabel 'obabel' not found in PATH. "
            "Install OpenBabel on this host (required to convert .gro to .xyz)."
        )


#: Multipliers turning a Gaussian ``mem`` value into GB. Gaussian accepts a
#: bare number (MB) plus MB/GB and the MW/GW word units. A bare number is MB,
#: which is why the packaged default reads ``32GB`` and must not be read as 32 MB.
_GAUSSIAN_MEM_GB = {
    "": 1 / 1024,
    "mb": 1 / 1024,
    "mw": 1 / 1024,
    "gb": 1.0,
    "gw": 1.0,
}


def gaussian_memory_gb(mem: object) -> float | None:
    """Parse a Gaussian ``mem`` setting into GB, or ``None`` if unparseable.

    ``32GB`` is 32 GB and ``32000MB`` is ~31 GB; both must be recognised, or the
    hardware guard silently under-reports a 32 GB request by three orders of
    magnitude and never blocks anything.
    """
    text = str(mem).strip().lower().replace(" ", "")
    if not text:
        return None
    end = 0
    while end < len(text) and (text[end].isdigit() or text[end] in ".+-"):
        end += 1
    number, unit = text[:end], text[end:]
    factor = _GAUSSIAN_MEM_GB.get(unit)
    if not number or factor is None:
        return None
    try:
        return float(number) * factor
    except ValueError:
        return None


def _qm_memory_gb(config_name: str) -> float | None:
    """RAM requested per QM job, in GB, from the active ORCA/Gaussian config."""
    from bimos.config.settings import settings
    from bimos.shared.user_config import resolve

    try:
        if settings.max_threads:
            data, _ = resolve(config_name, max_mode=True)
        else:
            data, _ = resolve(config_name)
    except (OSError, ValueError, KeyError):
        return None
    if config_name == "orca":
        maxcore = data.get("orca", {}).get("maxcore_mb")
        try:
            return float(maxcore) / 1024 if maxcore else None
        except (TypeError, ValueError):
            return None
    return gaussian_memory_gb(data.get("gaussian", {}).get("mem"))


def _effective_qm_jobs(config_name: str, jobs: int | None) -> int:
    """CLI --jobs wins; otherwise use the active YAML/MAX profile."""
    if jobs is not None:
        return jobs
    from bimos.config.settings import settings
    from bimos.quantum_chemistry.config import GaussianConfig, OrcaConfig

    config_cls = OrcaConfig if config_name == "orca" else GaussianConfig
    return config_cls.resolve(max_mode=settings.max_threads).max_jobs


def _run_qm(
    directory: str,
    jobs: int | None,
    charge: int,
    background: bool,
    gui: bool,
    kind: str,
    runner: Any,
    noun: str,
    config_name: str,
    force: bool = False,
) -> None:
    from bimos.shared import hardware

    effective_jobs = _effective_qm_jobs(config_name, jobs)
    hardware.guard(
        kind,
        hardware.assess_qm(_qm_memory_gb(config_name), effective_jobs),
        force=force,
    )

    def _run(emit: Any) -> Any:
        return runner(directory, max_jobs=jobs, charge=charge, on_output=emit)

    def _summarize(result: Any) -> None:
        click.echo(f"\nStatus: {result['status']}")
        click.echo(f"Updated {len(result['results'])} ITP files.")

    run_tracked(
        kind=kind,
        meta={"dir": directory},
        output=None,
        background=background,
        gui=gui,
        gui_message=f"Starting {noun} pipeline and opening dashboard...",
        run_fn=_run,
        summarize=_summarize,
    )


@click.command("qm-orca", epilog=QM_EPILOG)
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--jobs", "-j", type=click.IntRange(min=1), default=None, help="Max parallel QM calculations (defaults to the YAML/MAX profile).")
@click.option("--charge", "-q", default=0, help="Integer net charge of the ligands.")
@click.option("--background", "-b", is_flag=True, help="Run in background.")
@click.option("--gui", "-g", is_flag=True, help="Open GUI dashboard.")
@force_option
def qm_orca(
    directory: str, jobs: int | None, charge: int, background: bool, gui: bool, force: bool
) -> None:
    """Run full ORCA Hirshfeld pipeline on a directory of matching .gro + .itp pairs."""
    from bimos.quantum_chemistry import run_orca_pipeline

    _require_qm_toolchain("orca")
    _run_qm(
        directory, jobs, charge, background, gui, "qm-orca",
        run_orca_pipeline, "ORCA", "orca", force,
    )


@click.command("qm-g16", epilog=QM_EPILOG)
@click.argument("directory", type=click.Path(exists=True, file_okay=False))
@click.option("--jobs", "-j", type=click.IntRange(min=1), default=None, help="Max parallel QM calculations (defaults to the YAML/MAX profile).")
@click.option("--charge", "-q", default=0, help="Integer net charge of the ligands.")
@click.option("--background", "-b", is_flag=True, help="Run in background.")
@click.option("--gui", "-g", is_flag=True, help="Open GUI dashboard.")
@force_option
def qm_g16(
    directory: str, jobs: int | None, charge: int, background: bool, gui: bool, force: bool
) -> None:
    """Run full Gaussian Hirshfeld pipeline on a directory of matching .gro + .itp pairs."""
    from bimos.quantum_chemistry import run_gaussian_pipeline

    _require_qm_toolchain("g16")
    _run_qm(
        directory, jobs, charge, background, gui, "qm-g16",
        run_gaussian_pipeline, "Gaussian", "gaussian", force,
    )
