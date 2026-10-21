import functools
import logging
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

logger = logging.getLogger("bimos.chembl_db")

DATA_DIR = Path(__file__).parent / "data"

ALLOWED_TABLES = frozenset({"candidates", "phytocompounds"})

# CLI filter name -> (db column, comparator). Columns are allow-listed, so the
# generated SQL only ever contains these identifiers; values stay parameterized.
# NOTE: column names follow the legacy ChEMBL SQLite schema (Spanish identifiers)
# shipped in infrastructure/data/*.db; they are storage identifiers, not UI text.
FILTER_COLUMNS = {
    "min_mw": ("peso_mol", ">="),
    "max_mw": ("peso_mol", "<="),
    "min_logp": ("alogp", ">="),
    "max_logp": ("alogp", "<="),
    "max_hbd": ("donadores_h", "<="),
    "max_hba": ("aceptores_h", "<="),
    "max_rotables": ("enlaces_rotables", "<="),
    "max_tpsa": ("superficie_polar", "<="),
    "max_lipinski": ("violaciones_lipinski", "<="),
    "min_drug_likeness": ("drug_likeness", ">="),
    "natural_product": ("natural_product", "="),
    "min_phase": ("max_phase", ">="),
    "max_aromatic": ("anillos_aromaticos", "<="),
}

# Classic Lipinski / Veber drug-like defaults (None = no bound).
LIPINSKI_DEFAULTS = {
    "max_mw": 500.0,
    "max_logp": 5.0,
    "max_hbd": 5,
    "max_hba": 10,
    "max_rotables": 10,
}


def normalize_filters(filters: dict[str, Any] | None, *, druglike: bool = False) -> dict[str, float]:
    """Validate raw filter values; optionally seed Lipinski/Veber defaults."""
    active: dict[str, float] = dict(LIPINSKI_DEFAULTS) if druglike else {}
    for key, value in (filters or {}).items():
        if value is None:
            continue
        if key not in FILTER_COLUMNS:
            raise ValueError(f"Unknown filter '{key}'. Valid: {sorted(FILTER_COLUMNS)}.")
        try:
            number = float(value)
        except (TypeError, ValueError):
            raise ValueError(f"Filter '{key}' requires a number (got {value!r}).") from None
        active[key] = number
    _check_filter_ranges(active)
    return active


def _check_filter_ranges(active: dict[str, float]) -> None:
    pairs = (("min_mw", "max_mw"), ("min_logp", "max_logp"))
    for low, high in pairs:
        if low in active and high in active and active[low] > active[high]:
            raise ValueError(f"Inverted range: {low}={active[low]} > {high}={active[high]}.")


def apply_filters(base_sql: str, params: list[Any], filters: dict[str, float]) -> tuple[str, list[Any]]:
    """Append an AND-joined WHERE clause for *filters* (allow-listed columns only)."""
    clauses = []
    values = list(params)
    for key, number in filters.items():
        column, comparator = FILTER_COLUMNS[key]
        clauses.append(f"{column} {comparator} ?")
        values.append(number)
    if not clauses:
        return base_sql, values
    connector = " AND " if "WHERE" in base_sql.upper() else " WHERE "
    return base_sql + connector + " AND ".join(clauses), values


def _resolve_table_name(dataset_name: str, cursor: sqlite3.Cursor) -> str:
    table_name = "candidates" if "candidates" in dataset_name else "phytocompounds"
    if table_name not in ALLOWED_TABLES:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        row = cursor.fetchone()
        if not row:
            raise RuntimeError(f"No tables found in database for {dataset_name}")
        table_name = row[0]
    return table_name


def get_available_datasets() -> list[str]:
    if not DATA_DIR.exists():
        return []
    return [p.stem for p in DATA_DIR.glob("*.db")]


def export_to_sdf(
    dataset_name: str,
    output_path: Path,
    filters: dict[str, Any] | None = None,
    *,
    druglike: bool = False,
) -> int:
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Dataset {dataset_name} not found at {db_path}")
    active = normalize_filters(filters, druglike=druglike)

    with closing(sqlite3.connect(str(db_path))) as conn:
        cursor = conn.cursor()

        table_name = _resolve_table_name(dataset_name, cursor)

        try:
            sql, params = apply_filters(
                f"SELECT chembl_id, pref_name, canonical_smiles FROM {table_name}",  # nosec - table_name validated by _resolve_table_name
                [],
                active,
            )
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchone()
            if not tables:
                raise RuntimeError(f"No tables found in {db_path}") from None
            table_name = tables[0]
            sql, params = apply_filters(
                f"SELECT chembl_id, pref_name, canonical_smiles FROM {table_name}",  # nosec - table_name from sqlite_master
                [],
                active,
            )
            cursor.execute(sql, params)
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

    return count


def search_candidates(
    dataset_name: str,
    query: str,
    filters: dict[str, Any] | None = None,
    *,
    druglike: bool = False,
) -> list[dict[str, Any]]:
    # lru_cache needs hashable args: freeze the filter mapping.
    frozen = tuple(sorted((k, float(v)) for k, v in (normalize_filters(filters, druglike=druglike)).items()))
    # Defensive copy: the cached list is shared across calls.
    return [dict(row) for row in _search_cached(dataset_name, query, frozen)]


def count_candidates(
    dataset_name: str,
    query: str,
    filters: dict[str, Any] | None = None,
    *,
    druglike: bool = False,
) -> int:
    """Total matches for a text query + property filters (ignores the LIMIT)."""
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        return 0
    active = normalize_filters(filters, druglike=druglike)
    with closing(sqlite3.connect(str(db_path))) as conn:
        cursor = conn.cursor()
        table_name = _resolve_table_name(dataset_name, cursor)
        base = (
            f"SELECT COUNT(*) FROM {table_name} "  # nosec - table_name validated by _resolve_table_name
            "WHERE (pref_name LIKE ? OR chembl_id LIKE ? OR canonical_smiles LIKE ?)"
        )
        sql, params = apply_filters(base, [f"%{query}%", f"%{query}%", f"%{query}%"], active)
        cursor.execute(sql, params)
        row = cursor.fetchone()
    return int(row[0]) if row else 0


@functools.lru_cache(maxsize=128)
def _search_cached(
    dataset_name: str, query: str, frozen: tuple[tuple[str, float], ...]
) -> list[dict[str, Any]]:
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        return []

    with closing(sqlite3.connect(str(db_path))) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        table_name = _resolve_table_name(dataset_name, cursor)

        base = (
            f"SELECT * FROM {table_name} "  # nosec - table_name validated by _resolve_table_name
            "WHERE (pref_name LIKE ? OR chembl_id LIKE ? OR canonical_smiles LIKE ?)"
        )
        sql, params = apply_filters(base, [f"%{query}%", f"%{query}%", f"%{query}%"], dict(frozen))
        cursor.execute(sql + " LIMIT 50", params)
        results = [dict(row) for row in cursor.fetchall()]
    return results
