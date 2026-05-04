"""
Molecular docking pipeline using AutoDock Vina.

Workflow:
  1. Split multi-molecule SDF → individual .sdf files.
  2. Convert each ligand SDF → PDBQT (Meeko + RDKit, inside container).
  3. Convert receptor PDB → PDBQT (inside container).
  4. Compute grid box from receptor coordinates.
  5. Run Vina for each protein-ligand pair (configurable repetitions).
  6. Score results and copy the best pose to results/best/.
"""

import re
import shutil
import logging
from pathlib import Path
from typing import Callable, Optional

from bimos.config.settings import settings
from bimos.infrastructure import container

logger = logging.getLogger("bimos.docking")

# Default Vina parameters — robust defaults matching user scripts
DEFAULTS = {
    "times": 10,
    "margin": 1.0,
    "num_modes": 20,
    "exhaustiveness": 12,
    "energy_range": 3.0,
    "cpu_per_job": settings.get_threads(),
}

IMAGE = settings.bimos_image

# ── Utilities ─────────────────────────────────────────────────────────────────

def _split_sdf(sdf_path: Path, output_dir: Path) -> list[Path]:
    """Split a multi-molecule SDF into individual files."""
    output_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    current: list[str] = []
    mol_name: Optional[str] = None
    mol_count = 0
    seen: set[str] = set()

    with open(sdf_path) as fh:
        for line in fh:
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
                out.write_text("".join(current))
                created.append(out)
                current, mol_name = [], None

    return created


def _read_coords(pdbqt_path: Path) -> tuple[list[float], list[float], list[float]]:
    """Extract X/Y/Z coordinates from PDB or PDBQT ATOM/HETATM lines."""
    xs, ys, zs = [], [], []
    with open(pdbqt_path) as fh:
        for line in fh:
            if line.startswith(("ATOM", "HETATM")):
                try:
                    xs.append(float(line[30:38]))
                    ys.append(float(line[38:46]))
                    zs.append(float(line[46:54]))
                except ValueError:
                    continue
    return xs, ys, zs


def _grid_box_conf(
    pdbqt_path: Path,
    conf_path: Path,
    margin: float,
    num_modes: int,
    energy_range: float,
    exhaustiveness: int,
) -> None:
    """Write a Vina .conf file from receptor coordinates."""
    xs, ys, zs = _read_coords(pdbqt_path)
    if not xs:
        raise ValueError(f"No ATOM/HETATM coordinates found in {pdbqt_path}")

    cx = round(sum(xs) / len(xs), 3)
    cy = round(sum(ys) / len(ys), 3)
    cz = round(sum(zs) / len(zs), 3)
    sx = round(max(xs) - min(xs) + margin, 3)
    sy = round(max(ys) - min(ys) + margin, 3)
    sz = round(max(zs) - min(zs) + margin, 3)

    conf = (
        f"center_x = {cx}\n"
        f"center_y = {cy}\n"
        f"center_z = {cz}\n\n"
        f"size_x = {sx}\n"
        f"size_y = {sy}\n"
        f"size_z = {sz}\n\n"
        f"num_modes      = {num_modes}\n"
        f"energy_range   = {energy_range}\n"
        f"exhaustiveness = {exhaustiveness}\n"
    )
    conf_path.write_text(conf)


def _extract_best_score(pdbqt_file: Path) -> Optional[float]:
    """Extract the best binding affinity from a Vina output PDBQT."""
    with open(pdbqt_file) as fh:
        for line in fh:
            if line.startswith("REMARK VINA RESULT:"):
                try:
                    return float(line.split()[3])
                except (IndexError, ValueError):
                    continue
    return None


# ── Container helpers ─────────────────────────────────────────────────────────

def _container_run(cmd: list[str], work_dir: Path, on_output: Optional[Callable[[str], None]] = None) -> int:
    """Run a command inside the BIMOS container, mounting work_dir as /work."""
    return container.run(
        command=cmd,
        image=IMAGE,
        volumes={str(work_dir): "/work"},
        workdir="/work",
        on_output=on_output,
    )


def _prepare_receptor(pdb_path: Path, on_output: Optional[Callable[[str], None]] = None) -> Path:
    """Convert receptor PDB → PDBQT using Meeko."""
    pdbqt_path = pdb_path.with_suffix(".pdbqt")
    if pdbqt_path.exists():
        return pdbqt_path

    rc = _container_run(
        ["mk_prepare_receptor.py", "--read_pdb", pdb_path.name, "-p", pdbqt_path.name],
        work_dir=pdb_path.parent,
        on_output=on_output,
    )
    if rc != 0 or not pdbqt_path.exists():
        raise RuntimeError(f"Receptor preparation failed for {pdb_path.name} (exit {rc})")
    return pdbqt_path


_ADD_H_SCRIPT = """\
from rdkit import Chem
from rdkit.Chem import AllChem
import sys

sdf_in  = "{sdf_in}"
sdf_out = "{sdf_out}"

def largest_fragment(mol):
    frags = Chem.GetMolFrags(mol, asMols=True, sanitizeFrags=True)
    return max(frags, key=lambda m: m.GetNumHeavyAtoms())

suppl  = Chem.SDMolSupplier(sdf_in, removeHs=False)
writer = Chem.SDWriter(sdf_out)
ok = 0
for mol in suppl:
    if mol is None:
        continue
    mol = largest_fragment(mol)
    mol_h = Chem.AddHs(mol)
    if AllChem.EmbedMolecule(mol_h, AllChem.ETKDGv3()) == -1:
        continue
    AllChem.MMFFOptimizeMolecule(mol_h)
    writer.write(mol_h)
    ok += 1
writer.close()
if ok == 0:
    sys.exit(1)
"""


def _prepare_ligand(sdf_path: Path, on_output: Optional[Callable[[str], None]] = None) -> Optional[Path]:
    """Convert ligand SDF → PDBQT using RDKit (add Hs) + Meeko."""
    pdbqt_path = sdf_path.with_suffix(".pdbqt")
    if pdbqt_path.exists():
        return pdbqt_path

    sdf_h = sdf_path.with_name(sdf_path.stem + "_h.sdf")
    script_path = sdf_path.parent / f"_addhyd_{sdf_path.stem}.py"
    script_path.write_text(
        _ADD_H_SCRIPT.format(sdf_in=sdf_path.name, sdf_out=sdf_h.name)
    )

    try:
        rc = _container_run(["python3", script_path.name], work_dir=sdf_path.parent, on_output=on_output)
        if rc != 0:
            logger.warning("RDKit H-addition failed for %s", sdf_path.name)
            return None

        rc = _container_run(
            ["mk_prepare_ligand.py", "-i", sdf_h.name, "-o", pdbqt_path.name,
             "--charge_model", "gasteiger", "--rename_atoms"],
            work_dir=sdf_path.parent,
            on_output=on_output,
        )
        if rc != 0 or not pdbqt_path.exists():
            logger.warning("Meeko preparation failed for %s", sdf_path.name)
            return None
    finally:
        script_path.unlink(missing_ok=True)
        sdf_h.unlink(missing_ok=True)

    return pdbqt_path


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_docking_pipeline(
    protein_pdb: str,
    ligands_sdf: str,
    output_dir: Optional[str] = None,
    times: int = DEFAULTS["times"],
    margin: float = DEFAULTS["margin"],
    num_modes: int = DEFAULTS["num_modes"],
    exhaustiveness: int = DEFAULTS["exhaustiveness"],
    energy_range: float = DEFAULTS["energy_range"],
    cpu_per_job: int = DEFAULTS["cpu_per_job"],
    on_output: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Full docking pipeline.

    Args:
        protein_pdb: Path to the receptor PDB file.
        ligands_sdf: Path to the multi-molecule SDF file.
        output_dir: Where to store results.
        times: Number of Vina runs per pair.
        on_output: Line-by-line output callback.

    Returns:
        dict: status, results (list of best poses), output_dir
    """
    protein_path = Path(protein_pdb).resolve()
    ligands_path = Path(ligands_sdf).resolve()

    if not protein_path.exists():
        raise FileNotFoundError(f"Receptor PDB not found: {protein_path}")
    if not ligands_path.exists():
        raise FileNotFoundError(f"Ligands SDF not found: {ligands_path}")

    if output_dir:
        job_dir = Path(output_dir)
    else:
        job_dir = settings.workspace_path / "docking" / protein_path.stem
    job_dir.mkdir(parents=True, exist_ok=True)

    proteins_dir = job_dir / "proteins"
    ligands_dir  = job_dir / "ligands"
    results_dir  = job_dir / "results"
    bests_dir    = results_dir / "bests"
    for d in (proteins_dir, ligands_dir, results_dir, bests_dir):
        d.mkdir(parents=True, exist_ok=True)

    # Copy inputs
    pdb_dest = proteins_dir / protein_path.name
    shutil.copy2(protein_path, pdb_dest)
    shutil.copy2(ligands_path, ligands_dir / "ligands.sdf")

    # Step 1: Prepare receptor
    if on_output:
        on_output("[BIMOS] Step 1: Preparing receptor...")
    receptor_pdbqt = _prepare_receptor(pdb_dest, on_output=on_output)

    # Step 2: Split SDF
    if on_output:
        on_output("[BIMOS] Step 2: Splitting ligand SDF...")
    sdf_files = _split_sdf(ligands_dir / "ligands.sdf", ligands_dir)
    if not sdf_files:
        raise RuntimeError("No molecules found in the SDF file.")

    # Step 3: Prepare ligands
    if on_output:
        on_output(f"[BIMOS] Step 3: Preparing {len(sdf_files)} ligand(s)...")
    ligand_pdbqts: list[Path] = []
    for sdf in sdf_files:
        pdbqt = _prepare_ligand(sdf, on_output=on_output)
        if pdbqt:
            ligand_pdbqts.append(pdbqt)
        else:
            logger.warning("Skipping ligand %s (preparation failed)", sdf.name)

    if not ligand_pdbqts:
        raise RuntimeError("No ligands prepared successfully.")

    # Step 4: Dock each pair
    if on_output:
        on_output(f"[BIMOS] Step 4: Docking {len(ligand_pdbqts)} ligand(s) (times={times})...")

    # Compute grid box from receptor
    conf_path = proteins_dir / f"{protein_path.stem}.conf"
    _grid_box_conf(
        receptor_pdbqt, conf_path,
        margin=margin, num_modes=num_modes,
        energy_range=energy_range, exhaustiveness=exhaustiveness,
    )

    final_results: list[dict] = []

    for lig_pdbqt in ligand_pdbqts:
        complex_name = f"{protein_path.stem}-{lig_pdbqt.stem}"
        complex_dir  = results_dir / complex_name
        complex_dir.mkdir(parents=True, exist_ok=True)

        # Copy inputs into complex dir for container mounting
        shutil.copy2(receptor_pdbqt, complex_dir / receptor_pdbqt.name)
        shutil.copy2(lig_pdbqt, complex_dir / lig_pdbqt.name)
        shutil.copy2(conf_path, complex_dir / conf_path.name)

        from concurrent.futures import ThreadPoolExecutor

        def _run_single_vina(i: int):
            out_name = f"{complex_name}-{i}.pdbqt"
            rc = _container_run(
                [
                    "vina",
                    "--receptor", receptor_pdbqt.name,
                    "--ligand",   lig_pdbqt.name,
                    "--config",   conf_path.name,
                    "--out",      out_name,
                    "--cpu",      str(cpu_per_job),
                    "--exhaustiveness", str(exhaustiveness),
                ],
                work_dir=complex_dir,
                on_output=on_output,
            )
            out_path = complex_dir / out_name
            score = _extract_best_score(out_path) if rc == 0 else None
            return rc, out_path, score

        # Parallelize runs for this complex
        max_workers = max(1, settings.get_threads() // max(1, cpu_per_job))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            job_results = list(executor.map(_run_single_vina, range(1, times + 1)))

        scored: list[tuple[Path, float]] = []
        for rc, out_path, score in job_results:
            if rc == 0 and score is not None:
                scored.append((out_path, score))
            elif rc != 0:
                logger.warning("[%s] A Vina run failed", complex_name)

        if not scored:
            logger.warning("[%s] No successful docking results.", complex_name)
            continue

        scored.sort(key=lambda t: t[1])
        best_file, best_score = scored[0]
        shutil.copy2(best_file, bests_dir / best_file.name)

        final_results.append({
            "complex": complex_name,
            "best_pose": str(bests_dir / best_file.name),
            "best_score_kcal_mol": best_score,
        })

        if on_output:
            on_output(f"[BIMOS] [{complex_name}] Best score: {best_score:.3f} kcal/mol")

    if on_output:
        on_output(f"[BIMOS] Docking complete. {len(final_results)} complex(es) done.")
        on_output(f"[BIMOS] Results at: {results_dir}")

    return {
        "status": "completed",
        "results": final_results,
        "output_dir": str(job_dir),
    }
