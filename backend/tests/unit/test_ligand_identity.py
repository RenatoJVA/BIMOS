"""Unit tests for dual ligand identity (candidate vs internal name)."""

from pathlib import Path

import pytest

from bimos.shared.ligand_identity import (
    count_gro_atoms,
    count_itp_atoms,
    detect_gro_resname,
    gro_atom_lines,
    normalize_gro_resname,
    parse_gro_resnames,
    parse_itp_atom_residues,
    parse_itp_moleculetype,
    resolve_ligand_identity,
)


def _gro_text(resname: str, n: int = 3) -> str:
    atoms = "".join(
        f"{i + 1:>5d}{resname:<5s}{'C' + str(i):<5s}{i + 1:>5d}   1.000   1.000   1.000\n"
        for i in range(n)
    )
    return f"TITLE\n{n}\n{atoms}   5.000   5.000   5.000\n"


def _itp_text(mol: str, res: str, n: int = 3) -> str:
    atoms = "".join(
        f"     {i + 1}   opls_800      1    {res}   C{i:<3}  1     0.1000     12.0110\n"
        for i in range(n)
    )
    return f"[ moleculetype ]\n; Name  nrexcl\n{mol}   3\n[ atoms ]\n{atoms}\n"


def test_parse_gro_single_resname(tmp_path: Path) -> None:
    gro = tmp_path / "JZ4.gro"
    gro.write_text(_gro_text("JZ4"))
    assert parse_gro_resnames(gro) == {"JZ4": 3}
    assert detect_gro_resname(gro) == "JZ4"


def test_parse_gro_five_char_resname(tmp_path: Path) -> None:
    gro = tmp_path / "mol.gro"
    gro.write_text(_gro_text("LIGAN", n=2))
    assert detect_gro_resname(gro) == "LIGAN"


def test_detect_gro_mixed_raises(tmp_path: Path) -> None:
    gro = tmp_path / "mix.gro"
    gro.write_text(
        "TITLE\n2\n"
        f"{1:>5d}{'UNK':<5s}{'C1':<5s}{1:>5d}   1.000   1.000   1.000\n"
        f"{2:>5d}{'LIG':<5s}{'C2':<5s}{2:>5d}   2.000   2.000   2.000\n"
        "   5.000   5.000   5.000\n"
    )
    with pytest.raises(ValueError, match="multiple mixed residues"):
        detect_gro_resname(gro)


def test_detect_gro_short_raises(tmp_path: Path) -> None:
    gro = tmp_path / "short.gro"
    gro.write_text("TITLE\n0\n")
    with pytest.raises(ValueError, match="too short or empty"):
        detect_gro_resname(gro)


def test_parse_itp_moleculetype(tmp_path: Path) -> None:
    itp = tmp_path / "JZ4.itp"
    itp.write_text(_itp_text("JZ4", "JZ4"))
    assert parse_itp_moleculetype(itp) == "JZ4"
    assert parse_itp_atom_residues(itp) == {"JZ4"}


def test_parse_itp_moleculetype_missing_raises(tmp_path: Path) -> None:
    itp = tmp_path / "bad.itp"
    itp.write_text("[ atoms ]\n     1   CA      1   LIG  A    1  0.0  12.0\n")
    with pytest.raises(ValueError, match="moleculetype"):
        parse_itp_moleculetype(itp)


def test_resolve_consistent(tmp_path: Path) -> None:
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "JZ4.itp"
    gro.write_text(_gro_text("JZ4"))
    itp.write_text(_itp_text("JZ4", "JZ4"))
    identity = resolve_ligand_identity(gro, itp)
    assert identity.candidate == "JZ4"
    assert identity.gro_resname == "JZ4"
    assert identity.itp_moleculetype == "JZ4"
    assert identity.needs_gro_normalization is False
    assert identity.warnings == ()


def test_resolve_unk_internal_keeps_candidate(tmp_path: Path) -> None:
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "JZ4.itp"
    gro.write_text(_gro_text("UNK"))
    itp.write_text(_itp_text("UNK", "UNK"))
    identity = resolve_ligand_identity(gro, itp)
    assert identity.candidate == "JZ4"
    assert identity.itp_moleculetype == "UNK"
    assert identity.needs_gro_normalization is False


def test_resolve_mismatch_flags_normalization(tmp_path: Path) -> None:
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "JZ4.itp"
    gro.write_text(_gro_text("UNK"))
    itp.write_text(_itp_text("LIG", "LIG"))
    identity = resolve_ligand_identity(gro, itp)
    assert identity.needs_gro_normalization is True
    assert any("LIG" in w for w in identity.warnings)


def test_resolve_stem_mismatch_warns(tmp_path: Path) -> None:
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "lig.itp"
    gro.write_text(_gro_text("UNK"))
    itp.write_text(_itp_text("UNK", "UNK"))
    identity = resolve_ligand_identity(gro, itp)
    assert identity.candidate == "JZ4"
    assert any("different stems" in w for w in identity.warnings)


def test_normalize_gro_resname(tmp_path: Path) -> None:
    src = tmp_path / "JZ4.gro"
    dst = tmp_path / "out.gro"
    src.write_text(_gro_text("UNK", n=2))
    n = normalize_gro_resname(src, dst, "LIG")
    assert n == 2
    assert detect_gro_resname(dst) == "LIG"
    # Coordinates preserved: only columns 6-10 change.
    for old, new in zip(src.read_text().splitlines(), dst.read_text().splitlines(), strict=True):
        assert old[:5] == new[:5]
        assert old[10:] == new[10:]


def test_gro_atom_lines_exact_match(tmp_path: Path) -> None:
    gro = tmp_path / "mix.gro"
    gro.write_text(
        "TITLE\n3\n"
        f"{1:>5d}{'UNK':<5s}{'C1':<5s}{1:>5d}   1.000   1.000   1.000\n"
        f"{2:>5d}{'UNKY':<5s}{'C2':<5s}{2:>5d}   2.000   2.000   2.000\n"
        f"{3:>5d}{'UNK':<5s}{'C3':<5s}{3:>5d}   3.000   3.000   3.000\n"
        "   5.000   5.000   5.000\n"
    )
    assert len(gro_atom_lines(gro, "UNK")) == 2


def test_atom_counts(tmp_path: Path) -> None:
    gro = tmp_path / "JZ4.gro"
    itp = tmp_path / "JZ4.itp"
    gro.write_text(_gro_text("JZ4", n=4))
    itp.write_text(_itp_text("JZ4", "JZ4", n=4))
    assert count_gro_atoms(gro) == 4
    assert count_itp_atoms(itp) == 4
