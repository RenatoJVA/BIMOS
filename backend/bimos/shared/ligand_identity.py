"""Dual ligand identity: external candidate name vs internal GROMACS name.

External (candidate) name comes from the ligand file stem (e.g. ``JZ4`` from
``JZ4.gro``) and is only used for output directories and logs.

Internal name (e.g. ``UNK``/``LIG``) is parsed from the file *contents*
(GRO resname, ITP moleculetype, ITP ``[ atoms ]`` residue column) and drives
all GROMACS operations (genrestr, make_ndx, topology, complex merge).
The ITP moleculetype is the force-field authority on conflict.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger("bimos.ligand_identity")

_MOLECULETYPE_RE = re.compile(r"\[\s*moleculetype\s*\]", re.IGNORECASE)
_SECTION_RE = re.compile(r"^\s*\[")

# GRO layout constants: title (line 1), atom count (line 2), atoms, box (last).
_MIN_GRO_LINES = 4
_MIN_ATOM_LINE_LEN = 10
_MIN_ITP_ATOM_COLS = 5


@dataclass(frozen=True)
class LigandIdentity:
    """Resolved ligand names."""

    candidate: str
    gro_resname: str
    itp_moleculetype: str
    itp_atom_residues: frozenset[str] = field(default_factory=frozenset)
    warnings: tuple[str, ...] = ()
    needs_gro_normalization: bool = False


def parse_gro_resnames(gro: Path) -> Counter[str]:
    """Count residue names of every atom line in a .gro file.

    GRO layout: title (line 1), atom count (line 2), atoms, box (last line).
    Atom lines carry the residue name in columns 6-10 (``%-5s`` field).
    """
    lines = gro.read_text(errors="replace").splitlines()
    if len(lines) < _MIN_GRO_LINES:
        raise ValueError(f".gro file too short or empty: {gro}")
    try:
        natoms = int(lines[1].split()[0])
    except (IndexError, ValueError) as exc:
        raise ValueError(f"invalid atom count header at line 2 of {gro}") from exc
    atom_block = lines[2 : 2 + natoms]
    counts: Counter[str] = Counter()
    for line in atom_block:
        if len(line) < _MIN_ATOM_LINE_LEN:
            continue
        resname = line[5:10].strip()
        if resname:
            counts[resname] += 1
    if not counts:
        raise ValueError(f"Could not detect resname in {gro}")
    return counts


def detect_gro_resname(gro: Path) -> str:
    """Return the single residue name of a ligand .gro, or raise if mixed."""
    counts = parse_gro_resnames(gro)
    if len(counts) > 1:
        names = ", ".join(f"{name}({n})" for name, n in counts.most_common())
        raise ValueError(f".gro with multiple mixed residues in {gro}: {names}")
    return next(iter(counts))


def count_gro_atoms(gro: Path) -> int:
    """Return the number of atom lines in a .gro file."""
    return sum(parse_gro_resnames(gro).values())


def parse_itp_moleculetype(itp: Path) -> str:
    """Return the ``[ moleculetype ]`` name from an .itp file."""
    lines = itp.read_text(errors="replace").splitlines()
    for i, line in enumerate(lines):
        if _MOLECULETYPE_RE.search(line):
            for nxt in lines[i + 1 :]:
                stripped = nxt.strip()
                if not stripped or stripped.startswith(";"):
                    continue
                return stripped.split()[0]
            break
    raise ValueError(f"No [ moleculetype ] found in {itp}")


def parse_itp_atom_residues(itp: Path) -> set[str]:
    """Return the distinct residue names of the ``[ atoms ]`` section."""
    residues: set[str] = set()
    inside = False
    for line in itp.read_text(errors="replace").splitlines():
        if re.match(r"^\s*\[\s*atoms\s*\]", line, re.IGNORECASE):
            inside = True
            continue
        if inside and _SECTION_RE.match(line):
            break
        if not inside:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        parts = stripped.split()
        if len(parts) >= _MIN_ITP_ATOM_COLS:
            residues.add(parts[3])
    return residues


def count_itp_atoms(itp: Path) -> int:
    """Return the number of data rows in the ``[ atoms ]`` section."""
    count = 0
    inside = False
    for line in itp.read_text(errors="replace").splitlines():
        if re.match(r"^\s*\[\s*atoms\s*\]", line, re.IGNORECASE):
            inside = True
            continue
        if inside and _SECTION_RE.match(line):
            break
        if not inside:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if len(stripped.split()) >= _MIN_ITP_ATOM_COLS:
            count += 1
    return count


def resolve_ligand_identity(gro_path: Path, itp_path: Path) -> LigandIdentity:
    """Infer the dual ligand identity from file contents.

    Candidate = stem of the .gro file (never rewritten into the data).
    Internal = GRO resname / ITP moleculetype (ITP wins on conflict).
    """
    gro_path = Path(gro_path)
    itp_path = Path(itp_path)
    candidate = gro_path.stem
    warnings: list[str] = []

    if itp_path.stem != candidate:
        warnings.append(f"gro '{gro_path.name}' and itp '{itp_path.name}' have different stems; candidate={candidate}")

    gro_res = detect_gro_resname(gro_path)
    itp_mol = parse_itp_moleculetype(itp_path)
    itp_residues = frozenset(parse_itp_atom_residues(itp_path))

    if itp_residues and gro_res not in itp_residues:
        warnings.append(f"resname GRO={gro_res} not in ITP residue column={sorted(itp_residues)}")

    needs_norm = gro_res != itp_mol
    if needs_norm:
        warnings.append(
            f"internal GRO={gro_res} != moleculetype ITP={itp_mol}; "
            f"the force field wins ({itp_mol}), the working .gro copy is normalized"
        )

    for warning in warnings:
        logger.warning("%s: %s", candidate, warning)

    return LigandIdentity(
        candidate=candidate,
        gro_resname=gro_res,
        itp_moleculetype=itp_mol,
        itp_atom_residues=itp_residues,
        warnings=tuple(warnings),
        needs_gro_normalization=needs_norm,
    )


def normalize_gro_resname(src: Path, dst: Path, target: str) -> int:
    """Copy *src* to *dst* rewriting the GRO resname field to *target*.

    Only atom lines (all but title/count/box) are touched; columns 6-10
    (``line[5:10]``) are replaced with the target left-justified in width 5.
    Returns the number of rewritten atom lines.
    """
    lines = Path(src).read_text(errors="replace").splitlines(keepends=True)
    if len(lines) < _MIN_GRO_LINES:
        raise ValueError(f".gro file too short or empty: {src}")
    replacement = target.ljust(5)[:5]
    rewritten = 0
    out = [lines[0], lines[1]]
    for line in lines[2:-1]:
        if len(line) >= _MIN_ATOM_LINE_LEN and line[5:10].strip():
            line = line[:5] + replacement + line[10:]
            rewritten += 1
        out.append(line)
    out.append(lines[-1])
    Path(dst).write_text("".join(out))
    return rewritten


def gro_atom_lines(gro: Path, resname: str) -> list[str]:
    """Return atom lines of *gro* whose resname field equals *resname* exactly."""
    lines = Path(gro).read_text(errors="replace").splitlines(keepends=True)
    if len(lines) < _MIN_GRO_LINES:
        return []
    return [line for line in lines[2:-1] if len(line) >= _MIN_ATOM_LINE_LEN and line[5:10].strip() == resname]
