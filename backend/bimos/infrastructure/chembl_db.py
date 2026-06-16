
import sqlite3
import logging
import functools
from pathlib import Path
from typing import Any, List, Dict

logger = logging.getLogger("bimos.chembl_db")

DATA_DIR = Path(__file__).parent / "data"

ALLOWED_TABLES = frozenset({"candidates", "phytocompounds"})

def _resolve_table_name(dataset_name: str, cursor: sqlite3.Cursor) -> str:
    table_name = "candidates" if "candidates" in dataset_name else "phytocompounds"
    if table_name not in ALLOWED_TABLES:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"No tables found in database for {dataset_name}")
        table_name = row[0]
    return table_name

def get_available_datasets() -> List[str]:
    if not DATA_DIR.exists():
        return []
    return [p.stem for p in DATA_DIR.glob("*.db")]

def export_to_sdf(dataset_name: str, output_path: Path) -> int:
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Dataset {dataset_name} not found at {db_path}")

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    table_name = _resolve_table_name(dataset_name, cursor)

    try:
        cursor.execute(
            f"SELECT chembl_id, pref_name, canonical_smiles FROM {table_name}"  # nosec - table_name validated by _resolve_table_name
        )
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchone()
        if not tables:
            raise RuntimeError(f"No tables found in {db_path}")
        table_name = tables[0]
        cursor.execute(
            f"SELECT chembl_id, pref_name, canonical_smiles FROM {table_name}"  # nosec - table_name from sqlite_master
        )
        rows = cursor.fetchall()

    count = 0
    with open(output_path, "w") as f:
        for chembl_id, name, smiles in rows:
            if not smiles:
                continue
            mol_name = name if name and name != "None" else chembl_id
            f.write(f"{mol_name}\n")
            f.write("  BIMOS-EXPORTER\n\n")
            f.write("  0  0  0  0  0  0  0  0  0  0999 V2000\n")
            f.write("M  END\n")
            f.write(f"> <SMILES>\n{smiles}\n\n")
            f.write(f"> <ChEMBL_ID>\n{chembl_id}\n\n")
            f.write("$$$$\n")
            count += 1

    conn.close()
    return count


@functools.lru_cache(maxsize=32)
def search_candidates(dataset_name: str, query: str) -> list[dict[str, Any]]:
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    table_name = _resolve_table_name(dataset_name, cursor)

    sql = (
        f"SELECT * FROM {table_name} "  # nosec - table_name validated by _resolve_table_name
        "WHERE pref_name LIKE ? OR chembl_id LIKE ? OR canonical_smiles LIKE ? LIMIT 50"
    )
    cursor.execute(sql, (f"%{query}%", f"%{query}%", f"%{query}%"))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results
