
import sqlite3
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger("bimos.chembl_db")

# Path to the bundled databases
DATA_DIR = Path(__file__).parent / "data"

def get_available_datasets() -> List[str]:
    """Return list of available SQLite datasets (without .db extension)."""
    if not DATA_DIR.exists():
        return []
    return [p.stem for p in DATA_DIR.glob("*.db")]

def export_to_sdf(dataset_name: str, output_path: Path) -> int:
    """
    Export all compounds from a SQLite dataset to a multi-molecule SDF file.
    Note: This generates an SDF with SMILES in a property, 3D coordinates 
    will be generated later by the docking pipeline.
    """
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        raise FileNotFoundError(f"Dataset {dataset_name} not found at {db_path}")

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Determine table name (usually same as file stem or 'candidates'/'phytocompounds')
    table_name = "candidates" if "candidates" in dataset_name else "phytocompounds"
    
    try:
        cursor.execute(f"SELECT chembl_id, pref_name, canonical_smiles FROM {table_name}")
        rows = cursor.fetchall()
    except sqlite3.OperationalError:
        # Fallback: try to find any table
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchone()
        if not tables:
            raise RuntimeError(f"No tables found in {db_path}")
        table_name = tables[0]
        cursor.execute(f"SELECT chembl_id, pref_name, canonical_smiles FROM {table_name}")
        rows = cursor.fetchall()

    count = 0
    with open(output_path, "w") as f:
        for chembl_id, name, smiles in rows:
            if not smiles:
                continue
            
            mol_name = name if name and name != "None" else chembl_id
            
            # Write a minimal SDF record that RDKit can parse
            # We put the SMILES in a property so the docking pipeline can use it to build 3D
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

def search_candidates(dataset_name: str, query: str) -> List[Dict]:
    """Search for compounds in the SQLite database."""
    db_path = DATA_DIR / f"{dataset_name}.db"
    if not db_path.exists():
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    table_name = "candidates" if "candidates" in dataset_name else "phytocompounds"
    
    sql = f"SELECT * FROM {table_name} WHERE pref_name LIKE ? OR chembl_id LIKE ? OR canonical_smiles LIKE ? LIMIT 50"
    cursor.execute(sql, (f"%{query}%", f"%{query}%", f"%{query}%"))
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results
