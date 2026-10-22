from pathlib import Path

import pytest

from bimos.config.settings import settings
from bimos.quantum_chemistry.itp import update_itp_charges
from bimos.quantum_chemistry.pipeline import (
    GaussianPipeline,
    OrcaPipeline,
    parse_gaussian_hirshfeld_charges,
)


def _make_orca_pipeline(charge: int = 0):
    return OrcaPipeline(output_dir="/tmp", charge=charge)


def test_calc_multiplicity_even() -> None:
    pipeline = _make_orca_pipeline(charge=0)
    atoms = ["C 0.0 0.0 0.0", "C 1.0 0.0 0.0"]
    mult = pipeline._calc_multiplicity(atoms)
    assert mult == 1


def test_calc_multiplicity_odd() -> None:
    pipeline = _make_orca_pipeline(charge=0)
    atoms = ["N 0.0 0.0 0.0", "O 1.0 0.0 0.0"]
    mult = pipeline._calc_multiplicity(atoms)
    assert mult == 2


def test_calc_multiplicity_with_charge() -> None:
    pipeline = _make_orca_pipeline(charge=1)
    atoms = ["C 0.0 0.0 0.0", "C 1.0 0.0 0.0"]
    mult = pipeline._calc_multiplicity(atoms)
    assert mult == 2


def test_calc_multiplicity_iron() -> None:
    pipeline = _make_orca_pipeline(charge=0)
    atoms = ["Fe 0.0 0.0 0.0"]
    mult = pipeline._calc_multiplicity(atoms)
    assert mult == 1


def test_update_itp_charges(tmp_path: Path) -> None:
    itp_content = (
        "[ atoms ]\n"
        "; nr  type  resnr  residue  atom  cgnr  charge  mass\n"
        "     1      C      1    LIG     C      1   0.0000  12.011\n"
        "     2      C      1    LIG     C      2   0.0000  12.011\n"
        "     3      O      1    LIG     O      3   0.0000  16.000\n"
        "     4      H      1    LIG     H      4   0.0000   1.008\n"
    )
    itp_path = tmp_path / "ligand.itp"
    itp_path.write_text(itp_content)
    charges = [0.1234, -0.0567, -0.2345, 0.0456]
    result_path = update_itp_charges(itp_path, charges)
    assert result_path.exists()
    assert result_path.name == "ligand-hirsh.itp"
    content = result_path.read_text()
    assert "0.1234" in content
    assert "-0.0567" in content


def test_update_itp_charges_mismatch_raises(tmp_path: Path) -> None:
    itp_content = (
        "[ atoms ]\n"
        "     1      C      1    LIG     C      1   0.0000  12.011\n"
        "     2      C      1    LIG     C      2   0.0000  12.011\n"
        "     3      O      1    LIG     O      3   0.0000  16.000\n"
    )
    itp_path = tmp_path / "ligand.itp"
    itp_path.write_text(itp_content)
    charges = [0.1, 0.2]
    with pytest.raises(RuntimeError, match="More atoms in ITP than charges"):
        update_itp_charges(itp_path, charges)


def test_orca_pipeline_no_binary(tmp_path: Path) -> None:
    """The missing-binary path is what is under test, not the absence of ORCA.

    A developer machine (or CI image) that has ORCA installed would otherwise
    fail this test for the wrong reason.
    """
    if settings.orca_path and Path(settings.orca_path).exists():
        pytest.skip(f"ORCA is installed at {settings.orca_path}")
    pipeline = OrcaPipeline(output_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="ORCA binary not found"):
        pipeline.run(directory=str(tmp_path))


def test_gaussian_pipeline_no_binary(tmp_path: Path) -> None:
    """See test_orca_pipeline_no_binary: skipped when Gaussian is installed."""
    if settings.gaussian_path and Path(settings.gaussian_path).exists():
        pytest.skip(f"Gaussian is installed at {settings.gaussian_path}")
    pipeline = GaussianPipeline(output_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="Gaussian binary not found"):
        pipeline.run(directory=str(tmp_path))


def test_update_itp_skips_comments(tmp_path: Path) -> None:
    itp_content = (
        "[ atoms ]\n"
        "; comment line\n"
        "     1      C      1    LIG     C      1   0.0000  12.011\n"
    )
    itp_path = tmp_path / "ligand.itp"
    itp_path.write_text(itp_content)
    charges = [0.1234]
    result = update_itp_charges(itp_path, charges)
    content = result.read_text()
    assert "; comment" in content
    assert "0.1234" in content


def test_gaussian_charges_stop_before_hydrogens_summed_block(tmp_path: Path) -> None:
    """Regression guard: the second Hirshfeld table must not be appended.

    Gaussian prints a summary table with hydrogens summed into heavy atoms
    after the per-atom table. The old parser used ``parts[1:2]`` instead of
    ``parts[:1]`` to detect the ``Tot`` row, so it collected both tables and
    rejected every real calculation with ``22 ITP atoms vs 32 charges``.
    """
    log = tmp_path / "JZ4.log"
    log.write_text(
        " Hirshfeld charges, spin densities, dipoles, and CM5 charges using IRadAn=      5:\n"
        "     1  H    0.166247   0.000000\n"
        "     2  O   -0.200619   0.000000\n"
        "       Tot  -0.000020   0.000000\n"
        " Hirshfeld charges with hydrogens summed into heavy atoms:\n"
        "     2  O   -0.034372  -0.064556\n"
        "\n"
    )
    assert parse_gaussian_hirshfeld_charges(log) == pytest.approx([0.166247, -0.200619])


def test_gaussian_charges_are_empty_without_the_table(tmp_path: Path) -> None:
    log = tmp_path / "empty.log"
    log.write_text("Normal termination of Gaussian\n")
    assert parse_gaussian_hirshfeld_charges(log) == []
