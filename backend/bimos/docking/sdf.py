"""SDF file utilities for the docking pipeline."""

import re
from pathlib import Path


def split_multi_molecule_sdf(sdf_path: Path, output_dir: Path) -> list[Path]:
    """Split a multi-molecule SDF into individual files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    current: list[str] = []
    mol_name: str | None = None
    mol_count = 0
    seen: set[str] = set()

    with open(sdf_path, encoding="utf-8") as handle:
        for line in handle:
            if not current and not line.strip():
                continue
            current.append(line)
            if len(current) == 1:
                candidate = line.strip()
                if candidate:
                    mol_name = re.sub(r"[^\w\-.]+", "_", candidate)
            if line.strip() == "$$$$":
                mol_count += 1
                base = mol_name or f"mol_{mol_count}"
                name = base
                counter = 1
                while name in seen:
                    name = f"{base}_{counter}"
                    counter += 1
                seen.add(name)
                out = output_dir / f"{name}.sdf"
                out.write_text("".join(current), encoding="utf-8")
                created.append(out)
                current, mol_name = [], None
    return created
