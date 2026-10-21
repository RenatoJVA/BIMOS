"""Select best structure from prediction output directories.

Works with both the Boltz-1 and Boltz-2 output layouts. Boltz nests results
deeper in v2 (``model_N/boltz_results_<stem>/predictions/<record>/...``), so the
search is recursive and layout-agnostic.
"""

import json
from pathlib import Path
from typing import Any

_STRUCT_SUFFIXES = (".cif", ".pdb")


def _struct_for(json_path: Path) -> Path | None:
    """Locate the structure file that matches a ``confidence_*.json`` file."""
    stem = json_path.name.removeprefix("confidence_").removesuffix(".json")
    return next(
        (
            json_path.parent / f"{stem}{ext}"
            for ext in _STRUCT_SUFFIXES
            if (json_path.parent / f"{stem}{ext}").exists()
        ),
        None,
    )


def pick_best_boltz(pred_root: Path) -> dict[str, Any] | None:
    """Return the highest-scoring structure under *pred_root*, if any.

    Scans recursively so it works with the flat Boltz-1 layout
    (``<model>/confidence_*.json``) and the nested Boltz-2 layout
    (``<model>/boltz_results_*/predictions/<record>/confidence_*.json``).
    """
    if not pred_root.exists():
        return None
    best: dict[str, Any] | None = None
    for json_path in sorted(pred_root.rglob("confidence_*.json")):
        try:
            with json_path.open(encoding="utf-8") as handle:
                data = json.load(handle)
        except (OSError, json.JSONDecodeError):
            continue
        score = data.get("confidence_score")
        if not isinstance(score, int | float):
            continue
        struct = _struct_for(json_path)
        if struct is None:
            continue
        if best is None or score > best["score"]:
            best = {"score": float(score), "struct_path": struct, "json_path": json_path}
    return best
