from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from bimos.quantum_chemistry.pipeline import OrcaPipeline, GaussianPipeline
from bimos.quantum_chemistry.itp import update_itp_charges


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
    pipeline = OrcaPipeline(output_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="ORCA binary not found"):
        pipeline.run(directory=str(tmp_path))


def test_gaussian_pipeline_no_binary(tmp_path: Path) -> None:
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
