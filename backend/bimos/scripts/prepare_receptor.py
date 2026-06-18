"""
PDB-to-PDBQT conversion using Meeko Polymer API.
Bypasses mk_prepare_receptor.py CLI bugs.
"""

import sys
import argparse
from pathlib import Path

from meeko import Polymer, PDBQTWriterLegacy


def prepare_receptor(pdb_path: str, output_path: str) -> None:
    pdb_string = Path(pdb_path).read_text()
    polymer = Polymer.from_pdb_string(pdb_string, allow_bad_res=True)
    rigid_pdbqt, _ = PDBQTWriterLegacy.write_from_polymer(polymer)
    Path(output_path).write_text(rigid_pdbqt)
    print(f"Receptor prepared: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare receptor PDBQT from PDB")
    parser.add_argument("--input", required=True, help="Input PDB file")
    parser.add_argument("--output", required=True, help="Output PDBQT file")
    args = parser.parse_args()

    try:
        prepare_receptor(args.input, args.output)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
