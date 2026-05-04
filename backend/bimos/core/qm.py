"""
Quantum Mechanics (QM) module for BIMOS.
Provides automated pipelines for ORCA and Gaussian:
1. Input generation from GROMACS .gro files.
2. Calculation of multiplicity.
3. Execution of host binaries.
4. Extraction of Hirshfeld charges.
5. Updating GROMACS .itp files with new charges.
"""

import logging
import os
import pathlib
import re
import shutil
import subprocess
import time
from typing import Callable, Optional

from bimos.config.settings import settings
from bimos.infrastructure import container

logger = logging.getLogger("bimos.qm")

ATM_NUM = {
    "H": 1, "He": 2, "Li": 3, "Be": 4, "B": 5, "C": 6, "N": 7, "O": 8, "F": 9, "Ne": 10,
    "Na": 11, "Mg": 12, "Al": 13, "Si": 14, "P": 15, "S": 16, "Cl": 17, "K": 19, "Ca": 20,
}

# ── Common Utilities ──────────────────────────────────────────────────────────

def calc_multiplicity(xyz_lines: list[str], charge: int = 0) -> int:
    """Calculate multiplicity based on total number of electrons."""
    total_electrons = 0
    for line in xyz_lines:
        parts = line.split()
        if not parts:
            continue
        first = parts[0]
        if first.isdigit():
            z = int(first)
        else:
            z = ATM_NUM.get(first.upper())
            if z is None:
                raise ValueError(f"Unknown element: {first}. Add it to ATM_NUM table.")
        total_electrons += z
    
    total_electrons -= charge
    return 1 if total_electrons % 2 == 0 else 2


def update_itp_charges(itp_path: pathlib.Path, charges: list[float], output_path: Optional[pathlib.Path] = None) -> pathlib.Path:
    """Update a GROMACS .itp file with new atomic charges."""
    if output_path is None:
        output_path = itp_path.with_name(f"{itp_path.stem}-hirsh.itp")
    
    inside_atoms = False
    atom_index = 0

    with open(itp_path) as fin, open(output_path, "w") as fout:
        for line in fin:
            if re.match(r'^\s*\[\s*atoms\s*\]', line):
                inside_atoms = True
                fout.write(line)
                continue
            if inside_atoms and re.match(r'^\s*\[', line):
                inside_atoms = False
            if not inside_atoms or line.strip().startswith(";"):
                fout.write(line)
                continue

            parts = line.split()
            if len(parts) >= 8:
                if atom_index >= len(charges):
                    raise RuntimeError(f"More atoms in ITP than charges provided for {itp_path}")

                parts[6] = f"{charges[atom_index]:.4f}"
                fout.write(
                    f"{parts[0]:>6} {parts[1]:>10} {parts[2]:>6} "
                    f"{parts[3]:>7} {parts[4]:<4} {parts[5]:>6} "
                    f"{parts[6]:>10} {parts[7]:>10}\n"
                )
                atom_index += 1
            else:
                fout.write(line)
    
    return output_path

# ── ORCA Implementation ───────────────────────────────────────────────────────

def run_orca_pipeline(
    directory: str,
    max_jobs: int = 2,
    charge: int = 0,
    on_output: Optional[Callable[[str], None]] = None
) -> dict:
    """Run the full ORCA Hirshfeld pipeline on a directory."""
    dir_path = pathlib.Path(directory).resolve()
    orca_bin = settings.orca_path or "/home/ciim/orca_6_0_1/orca"
    
    if not pathlib.Path(orca_bin).exists():
        raise FileNotFoundError(f"ORCA binary not found at {orca_bin}")

    def log(msg: str):
        logger.info(msg)
        if on_output:
            on_output(f"[ORCA] {msg}")

    gro_files = sorted(dir_path.glob("*.gro"))
    log(f"Found {len(gro_files)} .gro files in {dir_path}")

    processes = []
    
    # 1. Generate inputs and launch
    for gro in gro_files:
        inp_path = gro.with_suffix(".inp")
        
        # Convert GRO to XYZ via obabel (on host)
        subprocess.run(
            ["obabel", str(gro), "-oxyz", "-O", str(dir_path / f"{gro.stem}.xyz")],
            check=True,
            capture_output=True
        )
        
        xyz_content = (dir_path / f"{gro.stem}.xyz").read_text().splitlines()
        atoms = xyz_content[2:]
        mult = calc_multiplicity(atoms, charge)
        
        # Write ORCA input
        with open(inp_path, "w") as f:
            f.write("! CAM-B3LYP def2-TZVP TightSCF RIJCOSX\n\n")
            f.write(f"%pal nprocs {settings.get_threads()} end\n")
            f.write("%maxcore 32000\n\n") # 32GB
            f.write("%scf\n  MaxIter 512\nend\n\n")
            f.write("%output\n  Print[P_Hirshfeld] 1\nend\n\n")
            f.write(f"* xyz {charge} {mult}\n")
            for line in atoms:
                f.write(line + "\n")
            f.write("*\n")

        # Launch ORCA
        out_path = inp_path.with_suffix(".out")
        out_file = open(out_path, "w")
        
        env = dict(os.environ)
        orca_dir = str(pathlib.Path(orca_bin).parent)
        env["PATH"] = orca_dir + ":" + env.get("PATH", "")
        env["LD_LIBRARY_PATH"] = orca_dir + ":" + env.get("LD_LIBRARY_PATH", "")
        env["OMP_NUM_THREADS"] = str(settings.get_threads())

        while True:
            processes = [p for p in processes if p[0].poll() is None]
            if len(processes) < max_jobs:
                break
            time.sleep(1)

        log(f"Launching ORCA for {gro.name}")
        p = subprocess.Popen(
            [orca_bin, inp_path.name],
            stdout=out_file,
            stderr=out_file,
            cwd=str(dir_path),
            env=env
        )
        processes.append((p, out_file, gro))

    # 2. Wait for all
    log("Waiting for ORCA calculations to complete...")
    for p, f, _ in processes:
        p.wait()
        f.close()

    # 3. Post-process (extract charges and update ITP)
    results = []
    for gro in gro_files:
        itp = gro.with_suffix(".itp")
        out = gro.with_suffix(".out")
        
        if not itp.exists():
            log(f"Warning: No ITP found for {gro.name}, skipping charge update.")
            continue
            
        if "ORCA TERMINATED NORMALLY" not in out.read_text(errors="replace"):
            log(f"Error: ORCA failed for {gro.name}")
            continue
            
        # Extract Hirshfeld charges
        charges = []
        inside = False
        pattern = re.compile(r'^\s*\d+\s+[A-Z][a-zA-Z]?\s+([-]?\d+\.\d+)')
        
        with open(out) as f:
            for line in f:
                if "HIRSHFELD ANALYSIS" in line:
                    inside = True
                    continue
                if inside and ("TOTAL" in line or "Sum" in line):
                    break
                if inside:
                    m = pattern.match(line)
                    if m:
                        charges.append(float(m.group(1)))
        
        if not charges:
            log(f"Error: Could not extract charges from {out.name}")
            continue
            
        log(f"Updating {itp.name} with {len(charges)} charges")
        updated_itp = update_itp_charges(itp, charges)
        results.append(str(updated_itp))

    return {"status": "completed", "results": results}

# ── Gaussian Implementation ───────────────────────────────────────────────────

def run_gaussian_pipeline(
    directory: str,
    max_jobs: int = 2,
    charge: int = 0,
    on_output: Optional[Callable[[str], None]] = None
) -> dict:
    """Run the full Gaussian Hirshfeld pipeline on a directory."""
    dir_path = pathlib.Path(directory).resolve()
    g16_bin = settings.gaussian_path or "/opt/g16/g16"
    
    if not pathlib.Path(g16_bin).exists():
        raise FileNotFoundError(f"Gaussian binary not found at {g16_bin}")

    def log(msg: str):
        logger.info(msg)
        if on_output:
            on_output(f"[Gaussian] {msg}")

    gro_files = sorted(dir_path.glob("*.gro"))
    log(f"Found {len(gro_files)} .gro files in {dir_path}")

    processes = []
    
    # 1. Generate inputs and launch
    for gro in gro_files:
        gjf_path = gro.with_suffix(".gjf")
        
        # Convert GRO to XYZ via obabel (on host)
        subprocess.run(
            ["obabel", str(gro), "-oxyz", "-O", str(dir_path / f"{gro.stem}.xyz")],
            check=True,
            capture_output=True
        )
        
        xyz_content = (dir_path / f"{gro.stem}.xyz").read_text().splitlines()
        atoms = xyz_content[2:]
        mult = calc_multiplicity(atoms, charge)
        
        # Write Gaussian input
        with open(gjf_path, "w") as f:
            f.write(f"%chk={gjf_path.stem}.chk\n")
            f.write(f"%mem=32GB\n")
            f.write(f"%nprocshared={settings.get_threads()}\n")
            f.write("# cam-b3lyp tzvp pop=hirshfeld scf=(xqc,maxcycle=512)\n\n")
            f.write(f"{gro.stem} QM calculation\n\n")
            f.write(f"{charge} {mult}\n")
            for line in atoms:
                f.write(line.strip() + "\n")
            f.write("\n")

        # Launch Gaussian
        log_path = gjf_path.with_suffix(".log")
        log_file = open(log_path, "w")
        
        while True:
            processes = [p for p in processes if p[0].poll() is None]
            if len(processes) < max_jobs:
                break
            time.sleep(1)

        log(f"Launching Gaussian for {gro.name}")
        p = subprocess.Popen(
            [g16_bin, gjf_path.name],
            stdout=log_file,
            stderr=log_file,
            cwd=str(dir_path)
        )
        processes.append((p, log_file, gro))

    # 2. Wait for all
    log("Waiting for Gaussian calculations to complete...")
    for p, f, _ in processes:
        p.wait()
        f.close()

    # 3. Post-process
    results = []
    for gro in gro_files:
        itp = gro.with_suffix(".itp")
        log_path = gro.with_suffix(".log")
        
        if not itp.exists():
            log(f"Warning: No ITP found for {gro.name}, skipping charge update.")
            continue
            
        if "Normal termination of Gaussian" not in log_path.read_text(errors="replace"):
            log(f"Error: Gaussian failed for {gro.name}")
            continue
            
        # Extract Hirshfeld charges
        charges = []
        inside = False
        pattern = re.compile(r'^\s*(\d+)\s+([A-Z][a-zA-Z]?)\s+([-]?\d+\.\d+)')
        
        with open(log_path) as f:
            for line in f:
                if "Hirshfeld charges, spin densities" in line:
                    inside = True
                    continue
                if not inside:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "Tot":
                    break
                m = pattern.match(line)
                if m:
                    charges.append(float(m.group(3)))
        
        if not charges:
            log(f"Error: Could not extract charges from {log_path.name}")
            continue
            
        log(f"Updating {itp.name} with {len(charges)} charges")
        updated_itp = update_itp_charges(itp, charges)
        results.append(str(updated_itp))

    return {"status": "completed", "results": results}
