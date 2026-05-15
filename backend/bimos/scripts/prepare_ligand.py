"""
RDKit molecular utility script for BIMOS.
Handles hydrogen addition, 3D coordinate generation, and optimization.
"""

import sys
import argparse
from rdkit import Chem
from rdkit.Chem import AllChem

def largest_fragment(mol):
    """Keep only the largest fragment of a molecule."""
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    if not frags:
        return mol
    return max(frags, key=lambda m: m.GetNumHeavyAtoms())

def prepare_molecule(sdf_in, sdf_out):
    """
    Load molecule from SDF, add hydrogens, generate 3D coords, and optimize.
    """
    suppl = Chem.SDMolSupplier(sdf_in, removeHs=False)
    writer = Chem.SDWriter(sdf_out)
    ok_count = 0
    
    for mol in suppl:
        if mol is None:
            continue
        
        # If the molecule has no atoms (dummy SDF), try to get it from SMILES property
        if mol.GetNumAtoms() == 0 and mol.HasProp("SMILES"):
            smiles = mol.GetProp("SMILES")
            mol_new = Chem.MolFromSmiles(smiles)
            if mol_new:
                if mol.HasProp("_Name"):
                    mol_new.SetProp("_Name", mol.GetProp("_Name"))
                mol = mol_new

        if mol.GetNumAtoms() == 0:
            continue

        mol = largest_fragment(mol)
        mol_h = Chem.AddHs(mol)
        
        # Generate 3D coordinates
        if AllChem.EmbedMolecule(mol_h, AllChem.ETKDGv3()) == -1:
            # Fallback for very small or tricky molecules
            if AllChem.EmbedMolecule(mol_h, useRandomCoords=True) == -1:
                continue
        
        try:
            AllChem.MMFFOptimizeMolecule(mol_h)
        except:
            pass
            
        writer.write(mol_h)
        ok_count += 1
        
    writer.close()
    return ok_count

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Prepare molecules with RDKit")
    parser.add_argument("--input", required=True, help="Input SDF file")
    parser.add_argument("--output", required=True, help="Output SDF file")
    
    args = parser.parse_args()
    
    count = prepare_molecule(args.input, args.output)
    if count == 0:
        print("Error: No molecules processed successfully.")
        sys.exit(1)
    print(f"Successfully processed {count} molecules.")
