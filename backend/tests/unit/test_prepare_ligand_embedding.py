"""The ligand preparation step must not drop strained polycycles.

ETKDG's bounds smoothing fails on some fused/bridged ring systems even though a
valid conformer exists. The screen silently skipped five such ligands until the
embedding step learned to relax its constraints.
"""

import importlib.util
from pathlib import Path

import pytest

# RDKit lives in the BIMOS container image, not in the pixi dev environment.
Chem = pytest.importorskip("rdkit.Chem")

SCRIPT = Path(__file__).parents[2] / "bimos" / "scripts" / "prepare_ligand.py"

# Strained bridged/fused polycycle from the curated library that failed ETKDG.
STRAINED = "CC1=CC(=O)[C@H]2[C@H]3[C@@H]1[C@@]2(C)CC[C@H]3C(C)C"


def _load_script():
    spec = importlib.util.spec_from_file_location("prepare_ligand", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def module():
    return _load_script()


def test_embed_recovers_a_molecule_that_fails_default_embedding(module):
    mol = Chem.AddHs(Chem.MolFromSmiles(STRAINED))
    from rdkit.Chem import AllChem

    assert AllChem.EmbedMolecule(Chem.AddHs(Chem.MolFromSmiles(STRAINED)), AllChem.ETKDGv3()) == -1

    assert module.embed(mol) is True
    assert mol.GetNumConformers() == 1


def test_prepare_molecule_keeps_every_input(module, tmp_path):
    from rdkit.Chem import AllChem

    source = tmp_path / "in.sdf"
    writer = Chem.SDWriter(str(source))
    for name, smiles in (("strained", STRAINED), ("plain", "CCO")):
        mol = Chem.MolFromSmiles(smiles)
        mol.SetProp("_Name", name)
        AllChem.Compute2DCoords(mol)
        writer.write(mol)
    writer.close()

    output = tmp_path / "out.sdf"
    assert module.prepare_molecule(str(source), str(output)) == 2

    prepared = [m for m in Chem.SDMolSupplier(str(output), removeHs=False) if m is not None]
    assert {m.GetProp("_Name") for m in prepared} == {"strained", "plain"}
    assert all(any(a.GetAtomicNum() == 1 for a in m.GetAtoms()) for m in prepared)
    assert all(m.GetNumConformers() == 1 for m in prepared)
