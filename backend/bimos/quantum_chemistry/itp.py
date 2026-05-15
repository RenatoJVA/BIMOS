"""GROMACS topology charge updates from QM results."""

import re
from pathlib import Path


def update_itp_charges(itp_path: Path, charges: list[float]) -> Path:
    """Write a copy of *itp_path* with Hirshfeld charges in the [ atoms ] section."""
    output_path = itp_path.with_name(f"{itp_path.stem}-hirsh.itp")
    inside_atoms = False
    atom_index = 0

    with open(itp_path, encoding="utf-8") as source, open(output_path, "w", encoding="utf-8") as dest:
        for line in source:
            if re.match(r"^\s*\[\s*atoms\s*\]", line):
                inside_atoms = True
                dest.write(line)
                continue
            if inside_atoms and re.match(r"^\s*\[", line):
                inside_atoms = False
            if not inside_atoms or line.strip().startswith(";"):
                dest.write(line)
                continue

            parts = line.split()
            if len(parts) >= 8:
                if atom_index >= len(charges):
                    raise RuntimeError(f"More atoms in ITP than charges for {itp_path}")
                parts[6] = f"{charges[atom_index]:.4f}"
                dest.write(
                    f"{parts[0]:>6} {parts[1]:>10} {parts[2]:>6} "
                    f"{parts[3]:>7} {parts[4]:<4} {parts[5]:>6} "
                    f"{parts[6]:>10} {parts[7]:>10}\n"
                )
                atom_index += 1
            else:
                dest.write(line)
    return output_path
