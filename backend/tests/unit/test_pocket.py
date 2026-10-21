"""Unit tests for pocket helpers (pure Python, no containers)."""

from pathlib import Path

import pytest

from bimos.docking.pocket import (
    box_from_extent,
    center_from_residues,
    parse_pocket_residues,
    read_sdf_first_molecule_coords,
)

SDF_ONE = """ref
  test

  2  1  0  0  0  0            999 V2000
   10.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
   12.0000    0.0000    0.0000 C   0  0  0  0  0  0  0  0  0  0  0  0
  1  2  1  0  0  0  0
M  END
"""

PDB_SMALL = """ATOM      1  CA  GLU A 375      10.000  10.000  10.000  1.00  0.00           C
ATOM      2  CB  GLU A 375      12.000  10.000  10.000  1.00  0.00           C
ATOM      3  NE2 HIS A 347       0.000   0.000   0.000  1.00  0.00           N
"""


def test_parse_simple_list() -> None:
    assert parse_pocket_residues("375,347,351") == [(None, 375), (None, 347), (None, 351)]


def test_parse_separators_and_chains() -> None:
    assert parse_pocket_residues("A:375; 347 351") == [("A", 375), (None, 347), (None, 351)]


def test_parse_range_and_dedup() -> None:
    assert parse_pocket_residues("375-377,376") == [(None, 375), (None, 376), (None, 377)]


def test_parse_chain_range() -> None:
    assert parse_pocket_residues("A:375-376") == [("A", 375), ("A", 376)]


def test_parse_invalid() -> None:
    for bad in ("", "   ", "ABC", "375-", "-380", "A:", "37.5", "0", "380-375"):
        with pytest.raises(ValueError):
            parse_pocket_residues(bad)


def test_parse_range_cap() -> None:
    with pytest.raises(ValueError, match="too wide"):
        parse_pocket_residues("1-99999")


def test_sdf_first_molecule(tmp_path: Path) -> None:
    sdf = tmp_path / "ref.sdf"
    sdf.write_text(SDF_ONE)
    coords, n = read_sdf_first_molecule_coords(sdf)
    assert n == 1
    assert len(coords) == 2
    assert coords[0][0] == pytest.approx(10.0)


def test_sdf_multi_molecule_uses_first(tmp_path: Path) -> None:
    sdf = tmp_path / "multi.sdf"
    sdf.write_text(SDF_ONE + "$$$$\n" + SDF_ONE + "$$$$\n")
    coords, n = read_sdf_first_molecule_coords(sdf)
    assert n == 2
    assert len(coords) == 2


def test_sdf_empty_raises(tmp_path: Path) -> None:
    sdf = tmp_path / "empty.sdf"
    sdf.write_text("")
    with pytest.raises(ValueError, match="Empty SDF"):
        read_sdf_first_molecule_coords(sdf)


def test_center_from_residues(tmp_path: Path) -> None:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text(PDB_SMALL)
    center, n, span = center_from_residues(pdb, [("A", 375)])
    assert center == pytest.approx((11.0, 10.0, 10.0))
    assert n == 2
    assert span == pytest.approx((2.0, 0.0, 0.0))


def test_center_from_residues_no_chain_filter(tmp_path: Path) -> None:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text(PDB_SMALL)
    center, n, _ = center_from_residues(pdb, [(None, 347)])
    assert center == pytest.approx((0.0, 0.0, 0.0))
    assert n == 1


def test_center_from_residues_no_match(tmp_path: Path) -> None:
    pdb = tmp_path / "rec.pdb"
    pdb.write_text(PDB_SMALL)
    with pytest.raises(ValueError, match="No atom matches"):
        center_from_residues(pdb, [(None, 999)])


def test_box_from_extent_padding() -> None:
    assert box_from_extent((10.0, 8.0, 6.0), 4.0) == (14.0, 12.0, 10.0)


def test_box_from_extent_floor() -> None:
    assert box_from_extent((2.0, 0.0, 0.0), 4.0) == (6.0, 5.0, 5.0)


def test_box_negative_padding_raises() -> None:
    with pytest.raises(ValueError, match="Invalid padding"):
        box_from_extent((10.0, 10.0, 10.0), -1.0)
