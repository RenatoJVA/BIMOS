"""Select best structure from prediction output directories."""

import json
from pathlib import Path


def pick_best_esmfold(pred_dir: Path) -> dict | None:
    """Return the highest-confidence ESMFold result under *pred_dir*."""
    best: dict | None = None
    for json_path in pred_dir.rglob("confidence_*.json"):
        try:
            with open(json_path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        score = data.get("confidence_score") or data.get("plddt", 0)
        pdb = json_path.parent / f"{json_path.stem.replace('confidence_', '')}.pdb"
        if pdb.exists() and (best is None or score > best["score"]):
            best = {"score": score, "pdb_path": str(pdb)}
    return best


def pick_best_boltz(pred_root: Path) -> dict | None:
    """Return the highest-confidence Boltz result under *pred_root*."""
    best: dict | None = None
    for json_path in pred_root.rglob("confidence_*.json"):
        try:
            with open(json_path, encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        score = data.get("confidence_score")
        if score is None:
            continue
        stem = json_path.name.replace("confidence_", "").replace(".json", "")
        parent = json_path.parent
        struct = next(
            (parent / f"{stem}{ext}" for ext in (".cif", ".pdb") if (parent / f"{stem}{ext}").exists()),
            None,
        )
        if struct and (best is None or score > best["score"]):
            best = {"score": score, "struct_path": struct, "json_path": json_path}
    return best
