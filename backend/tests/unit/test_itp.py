from pathlib import Path
from bimos.quantum_chemistry.itp import update_itp_charges


def test_update_itp_charges_basic(tmp_path: Path) -> None:
    itp = tmp_path / "mol.itp"
    itp.write_text(
        "[ atoms ]\n"
        "     1   CA      1   LIG  A    1       0.0000     12.0110\n"
        "     2   CB      1   LIG  A    1       0.0000     12.0110\n"
    )
    charges = [-0.5, 0.3]
    out = update_itp_charges(itp, charges)
    assert out.exists()
    assert out.name == "mol-hirsh.itp"
    content = out.read_text()
    assert "-0.5000" in content
    assert "0.3000" in content


def test_update_itp_skips_comments(tmp_path: Path) -> None:
    itp = tmp_path / "mol.itp"
    itp.write_text(
        "[ atoms ]\n"
        "; this is a comment\n"
        "     1   CA      1   LIG  A    1       0.0000     12.0110\n"
    )
    charges = [0.5]
    out = update_itp_charges(itp, charges)
    content = out.read_text()
    assert "0.5000" in content
    assert "this is a comment" in content


def test_update_itp_raises_on_mismatch(tmp_path: Path) -> None:
    itp = tmp_path / "mol.itp"
    itp.write_text(
        "[ atoms ]\n"
        "     1   CA      1   LIG  A    1       0.0000     12.0110\n"
        "     2   CB      1   LIG  A    1       0.0000     12.0110\n"
    )
    charges = [0.5]
    import pytest
    with pytest.raises(RuntimeError, match="More atoms in ITP than charges"):
        update_itp_charges(itp, charges)


def test_update_itp_outside_atoms_section_unchanged(tmp_path: Path) -> None:
    itp = tmp_path / "mol.itp"
    itp.write_text(
        "[ bondtypes ]\n"
        "     1    2    1    0.15  500.0\n"
        "[ atoms ]\n"
        "     1   CA      1   LIG  A    1       0.0000     12.0110\n"
    )
    charges = [0.42]
    out = update_itp_charges(itp, charges)
    content = out.read_text()
    assert "0.4200" in content
    assert "bondtypes" in content
