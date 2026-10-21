"""Pocket helpers for targeted (non-blind) docking.

Three ways to define the Vina search box, in priority order:

1. Explicit ``center`` + ``size`` (angstroms, receptor frame).
2. ``center_on``: centroid of a reference ligand SDF (same frame as receptor).
3. ``pocket_residues``: centroid of receptor residues, e.g. ``"375,347,351"``.

Everything here is pure Python (no RDKit/container) so it fails fast with a
clear message before any container work starts.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger("bimos.docking.pocket")

# A box smaller than this is almost surely a user mistake (Vina needs > 0,
# and sub-5A boxes rarely cover a drug-like ligand).
MIN_BOX_SIZE = 5.0
# Upper sanity bound: larger boxes are allowed but logged as effectively blind.
LARGE_BOX_WARN = 30.0
# DoS guard for range expansion like "1-99999".
_MAX_RESIDUES_TOTAL = 1000
_MAX_RANGE_SPAN = 500
# PDB/PDBQT column layout: ATOM/HETATM lines carry xyz at fixed columns.
_MIN_PDB_LINE_LEN = 54
_MIN_SDF_LINES = 4
_MIN_V30_PARTS = 7

_RES_PATTERN = re.compile(r"^(?:(?P<chain>[A-Za-z]):)?(?P<start>\d+)(?:-(?P<end>\d+))?$")


def parse_pocket_residues(spec: str) -> list[tuple[str | None, int]]:
    """Parse ``"A:375, 347, 351-355"`` into ``[(chain|None, resnum)]``.

    Separators ``,``/``;``/whitespace are equivalent. Ranges expand
    (capped). Raises :class:`ValueError` with examples on bad input.
    """
    if not spec or not spec.strip():
        raise ValueError(
            "Empty pocket. Valid examples: '375,347,351', 'A:375-380', 'A:375 B:12'."
        )
    selection: list[tuple[str | None, int]] = []
    for raw in re.split(r"[,\s;]+", spec.strip()):
        if not raw:
            continue
        match = _RES_PATTERN.match(raw)
        if not match:
            raise ValueError(
                f"Invalid residue '{raw}'. Use NNN, NNN-MMM or C:NNN (e.g. 'A:375,347,351-355')."
            )
        chain = match.group("chain")
        start = int(match.group("start"))
        end = int(match.group("end") or start)
        if start < 1 or end < 1:
            raise ValueError(f"Invalid residue '{raw}': numbers start at 1.")
        if end < start:
            raise ValueError(f"Inverted range '{raw}': use NNN-MMM with MMM >= NNN.")
        if end - start > _MAX_RANGE_SPAN:
            raise ValueError(f"Range '{raw}' too wide (max {_MAX_RANGE_SPAN}).")
        for resnum in range(start, end + 1):
            selection.append((chain.upper() if chain else None, resnum))
        if len(selection) > _MAX_RESIDUES_TOTAL:
            raise ValueError(f"Selection too large (max {_MAX_RESIDUES_TOTAL} residues).")
    # De-duplicate preserving order.
    seen: set[tuple[str | None, int]] = set()
    unique = [item for item in selection if not (item in seen or seen.add(item))]  # type: ignore[func-returns-value]
    if not unique:
        raise ValueError("Empty pocket after parsing. Example: '375,347,351'.")
    return unique


def read_pdb_coords(path: Path) -> list[tuple[str, int, float, float, float]]:
    """Read ``(chain, resnum, x, y, z)`` from ATOM/HETATM lines of PDB/PDBQT."""
    coords = []
    for line in Path(path).read_text(errors="replace").splitlines():
        if not line.startswith(("ATOM", "HETATM")) or len(line) < _MIN_PDB_LINE_LEN:
            continue
        try:
            coords.append(
                (
                    line[21].strip().upper() or " ",
                    int(line[22:26].strip()),
                    float(line[30:38]),
                    float(line[38:46]),
                    float(line[46:54]),
                )
            )
        except ValueError:
            continue
    if not coords:
        raise ValueError(f"No readable ATOM/HETATM coordinates in {path}")
    return coords


def center_from_residues(
    pdb_path: Path, selection: list[tuple[str | None, int]]
) -> tuple[tuple[float, float, float], int, tuple[float, float, float]]:
    """Centroid, atom count and span of the selected receptor residues."""
    wanted = set(selection)
    picked = [
        (x, y, z)
        for chain, resnum, x, y, z in read_pdb_coords(pdb_path)
        if (None, resnum) in wanted or (chain, resnum) in wanted
    ]
    if not picked:
        available = sorted({resnum for _, resnum, *_ in read_pdb_coords(pdb_path)})
        raise ValueError(
            "No atom matches the pocket. "
            f"Available residues in receptor: {available[0]}-{available[-1]}."
        )
    return _centroid_span(picked)


def read_sdf_first_molecule_coords(sdf_path: Path) -> tuple[list[tuple[float, float, float]], int]:
    """Coordinates of the first molecule in an SDF (V2000, best-effort V3000).

    Returns ``(coords, n_molecules)``. Raises :class:`ValueError` if empty.
    """
    text = Path(sdf_path).read_text(errors="replace")
    blocks = [block for block in text.split("$$$$") if block.strip()]
    if not blocks:
        raise ValueError(f"Empty SDF or no molecules: {sdf_path}")
    coords = _parse_sdf_block(blocks[0].splitlines(), sdf_path)
    if not coords:
        raise ValueError(f"No readable atoms in the first molecule of {sdf_path}")
    if len(blocks) > 1:
        logger.warning("%s: %d molecules, using only the first", sdf_path.name, len(blocks))
    return coords, len(blocks)


def _parse_sdf_block(lines: list[str], source: Path) -> list[tuple[float, float, float]]:
    if any("V3000" in line for line in lines[:8]):
        return _parse_sdf_v3000(lines)
    if len(lines) < _MIN_SDF_LINES:
        raise ValueError(f"SDF block too short in {source}")
    try:
        n_atoms = int(lines[3][0:3].strip())
    except ValueError:
        raise ValueError(f"Unreadable count line in {source}: '{lines[3].strip()}'") from None
    if n_atoms < 1:
        return []
    coords = []
    for line in lines[4 : 4 + n_atoms]:
        try:
            coords.append((float(line[0:10]), float(line[10:20]), float(line[20:30])))
        except ValueError:
            continue
    return coords


def _parse_sdf_v3000(lines: list[str]) -> list[tuple[float, float, float]]:
    coords = []
    for line in lines:
        parts = line.split()
        if len(parts) >= _MIN_V30_PARTS and parts[0] == "M" and parts[1] == "V30" and parts[2].isdigit():
            try:
                coords.append((float(parts[4]), float(parts[5]), float(parts[6])))
            except ValueError:
                continue
    return coords


def _centroid_span(
    coords: list[tuple[float, float, float]],
) -> tuple[tuple[float, float, float], int, tuple[float, float, float]]:
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    zs = [c[2] for c in coords]
    center = (
        sum(xs) / len(xs),
        sum(ys) / len(ys),
        sum(zs) / len(zs),
    )
    span = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
    return center, len(coords), span


def box_from_extent(span: tuple[float, float, float], padding: float) -> tuple[float, float, float]:
    """Box sizes from an object span plus *padding* (same convention as auto margin)."""
    if not padding >= 0:
        raise ValueError(f"Invalid padding {padding}: must be >= 0.")
    sizes = []
    for axis in span:
        size = axis + padding
        if size < MIN_BOX_SIZE:
            logger.warning("Axis with span %.2f -> minimum box %.1f A", axis, MIN_BOX_SIZE)
            size = MIN_BOX_SIZE
        sizes.append(size)
    return (sizes[0], sizes[1], sizes[2])
