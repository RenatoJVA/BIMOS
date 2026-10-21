"""Screening cascade report (CSV)."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

COLUMNS = (
    "rank",
    "candidate",
    "vina_score_kcal_mol",
    "selected",
    "qm_backend",
    "hirsh_itp",
    "holo_dir",
    "holo_ok",
    "error",
)


def write_screen_report(path: str | Path, rows: list[dict[str, Any]]) -> Path:
    """Write ranked cascade hits to *path* as CSV and return it."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(COLUMNS), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return out
