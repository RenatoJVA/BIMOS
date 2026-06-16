from pathlib import Path
from bimos.docking.sdf import split_multi_molecule_sdf


def test_split_single_molecule(tmp_path: Path) -> None:
    sdf = tmp_path / "ligands.sdf"
    sdf.write_text("lig1\n  BIMOS\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n")
    out = tmp_path / "split"
    result = split_multi_molecule_sdf(sdf, out)
    assert len(result) == 1
    assert result[0].exists()


def test_split_multiple_molecules(tmp_path: Path) -> None:
    sdf = tmp_path / "multi.sdf"
    sdf.write_text(
        "lig1\n  BIMOS\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n"
        "lig2\n  BIMOS\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n"
    )
    out = tmp_path / "split"
    result = split_multi_molecule_sdf(sdf, out)
    assert len(result) == 2


def test_split_molecule_no_name(tmp_path: Path) -> None:
    sdf = tmp_path / "unnamed.sdf"
    sdf.write_text("\n  BIMOS\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n")
    out = tmp_path / "split"
    result = split_multi_molecule_sdf(sdf, out)
    assert len(result) == 1


def test_split_duplicate_names(tmp_path: Path) -> None:
    sdf = tmp_path / "dup.sdf"
    sdf.write_text(
        "mol\n  BIMOS\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n"
        "mol\n  BIMOS\n\n  0  0  0  0  0  0  0  0  0  0999 V2000\nM  END\n$$$$\n"
    )
    out = tmp_path / "split"
    result = split_multi_molecule_sdf(sdf, out)
    assert len(result) == 2
    assert result[0].stem == "mol"
    assert result[1].stem == "mol_1"


def test_split_empty_sdf_returns_empty(tmp_path: Path) -> None:
    sdf = tmp_path / "empty.sdf"
    sdf.write_text("")
    out = tmp_path / "split"
    result = split_multi_molecule_sdf(sdf, out)
    assert result == []
