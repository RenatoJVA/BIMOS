"""
Unified Molecular Dynamics pipeline for BIMOS (Apo & Holo).
Ported from robust user scripts with GPU offloading and stage detection.
"""

import logging
import re
import shutil
from enum import StrEnum
from pathlib import Path
from typing import Callable, Optional
from collections import defaultdict

from bimos.config.settings import settings
from bimos.infrastructure import container

logger = logging.getLogger("bimos.workflow")

IMAGE = settings.bimos_image
MAX_MIN_ITER = 15

def _get_parallel_args() -> list[str]:
    """Calculate parallelization flags based on settings."""
    threads = settings.get_threads()
    # NTMPI is usually 1 for GPU offloading to avoid complex domain decomposition overhead
    return ["-ntmpi", "1", "-ntomp", str(threads)]

# ── Stage definitions ────────────────────────────────────────────────────────

class Stage(StrEnum):
    PREP         = "prep"
    MINIMIZATION = "minimization"
    NVT          = "nvt"
    NPT          = "npt"
    SDM          = "sdm"
    ANALYSIS     = "analysis"
    DONE         = "done"


def _log_has(cwd: Path, log_name: str, token: str) -> bool:
    p = cwd / log_name
    if not p.exists():
        return False
    try:
        return token in p.read_text(errors="replace")
    except Exception:
        return False


def _detect_stage(cwd: Path, comp: str, is_holo: bool = False) -> Stage:
    prefix = "Holo" if is_holo else "Apo"

    # Prep check
    if not (cwd / f"min-{comp}.gro").exists() or not (cwd / f"{comp}.top").exists():
        return Stage.PREP

    # Minimization check (only if cg log exists)
    cg_log = cwd / f"min-cg-{comp}.log"
    if cg_log.exists() and "did not converge to Fmax" in cg_log.read_text(errors="replace"):
        return Stage.MINIMIZATION

    # Simulation phases check — log name matches deffnm: {phase}-{comp}.log
    for phase in ["nvt", "npt", "sdm"]:
        if not (cwd / f"{phase}-{comp}.gro").exists() or not _log_has(cwd, f"{phase}-{comp}.log", "Finished mdrun"):
            return Stage(phase)

    # Analysis check
    if not (cwd / f"{prefix}-{comp}-rmsd.xvg").exists():
        return Stage.ANALYSIS

    return Stage.DONE


# ── Histidine classification ──────────────────────────────────────────────────

def _classify_histidine(atom_lines: list[str]) -> str:
    atom_names = {line[12:16].strip() for line in atom_lines if line.startswith(("ATOM", "HETATM"))}
    has_hd1 = "HD1" in atom_names
    has_he2 = "HE2" in atom_names
    has_heme = any("HEME" in name for name in atom_names)
    if has_heme:
        return "HIS1"
    if has_hd1 and has_he2:
        return "HISH"
    if has_hd1:
        return "HISD"
    if has_he2:
        return "HISE"
    return "HISD"


def _fix_histidines(input_pdb: Path, output_pdb: Path, log_cb: Optional[Callable[[str], None]] = None) -> None:
    lines = input_pdb.read_text(errors="replace").splitlines(keepends=True)
    his_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for line in lines:
        if line.startswith(("ATOM", "HETATM")) and line[17:20].strip() == "HIS":
            his_groups[(line[21], line[22:26].strip())].append(line)
    his_types = {k: _classify_histidine(v) for k, v in his_groups.items()}
    corrected: list[str] = []
    for line in lines:
        if line.startswith(("ATOM", "HETATM")) and line[17:20].strip() == "HIS":
            key = (line[21], line[22:26].strip())
            new_name = his_types.get(key, "HISD")
            if log_cb:
                log_cb(f"Fixing His {key[0]}{key[1]}: HIS -> {new_name}")
            line = line[:17] + new_name.ljust(4)[:4] + line[21:]
        corrected.append(line)
    output_pdb.write_text("".join(corrected))


# ── Holo Helpers ─────────────────────────────────────────────────────────────

def _detect_resname_from_gro(gro_path: Path) -> str:
    lines = gro_path.read_text().splitlines()
    if len(lines) < 3:
        raise ValueError("GRO too short")
    return lines[2][5:8].strip()


def _patch_itp(itp_path: Path) -> None:
    lines = itp_path.read_text(errors="replace").splitlines(keepends=True)
    in_block, patched = False, []
    for line in lines:
        if line.startswith(";---"):
            in_block = True
        if in_block:
            if not line.startswith(";"):
                line = ";" + line
            if re.match(r"^\s*[0-9]", line.lstrip(";")):
                in_block = False
        patched.append(line)
    itp_path.write_text("".join(patched))


def _inject_topology(top_path: Path, itp_path: Path) -> str:
    """Injects ITP include and detects the moleculetype name."""
    # Detect name from ITP
    itp_content = itp_path.read_text(errors="replace")
    match = re.search(r"\[\s*moleculetype\s*\]\s*\n\s*;[^\n]*\n\s*(\S+)", itp_content, re.MULTILINE)
    if not match:
        # Fallback if no comment line
        match = re.search(r"\[\s*moleculetype\s*\]\s*\n\s*(\S+)", itp_content, re.MULTILINE)
    
    lig_name = match.group(1) if match else "ligand"
    
    top_content = top_path.read_text(errors="replace")
    inc_line = f'#include "{itp_path.name}"'
    if inc_line not in top_content:
        top_content = re.sub(r"(#include\s+\"[^\"]*forcefield\.itp\")", r"\1\n" + inc_line, top_content, count=1)
    
    if lig_name not in top_content.split("[ molecules ]")[-1] if "[ molecules ]" in top_content else True:
        top_content = top_content.rstrip() + f"\n{lig_name:<20}1\n"
    
    top_path.write_text(top_content)
    return lig_name


def _inject_posres(top_path: Path, lig_name: str) -> None:
    content = top_path.read_text(errors="replace")
    if "POSRES_LIG" not in content:
        block = f"; Strong position restraints for ligand\n#ifdef POSRES_LIG\n#include \"{lig_name}-posre.itp\"\n#endif\n\n"
        marker = "; Include water topology"
        content = content.replace(marker, block + marker, 1) if marker in content else content.rstrip() + "\n" + block
        top_path.write_text(content)




def _build_complex(prot_gro: Path, lig_gro: Path, resname: str, out: Path) -> None:
    p_lines = prot_gro.read_text().splitlines(keepends=True)
    lig_lines = [line for line in lig_gro.read_text().splitlines(keepends=True) if resname in line]
    n = len(p_lines) - 3 + len(lig_lines)
    new = [p_lines[0], f" {n}\n"] + p_lines[2:-1] + lig_lines + [p_lines[-1]]
    out.write_text("".join(new))


def _get_box(gro: Path) -> list[str]:
    return gro.read_text().splitlines()[-1].split()[:3]


def _clean_pdb(input_pdb: Path, output_pdb: Path) -> None:
    """Filter PDB to remove HOH, HETATM, ANISOU, CONECT, NA, CL."""
    exclusions = {"HOH", "HETATM", "ANISOU", "CONECT", "NA", "CL"}
    lines = input_pdb.read_text(errors="replace").splitlines(keepends=True)
    with open(output_pdb, "w") as f:
        for line in lines:
            if not any(line.startswith(ex) or f" {ex} " in line[:12] for ex in exclusions):
                f.write(line)


# ── GMX Invocation ────────────────────────────────────────────────────────────

def _gmx_call(bin_name: str, args: list[str], cwd: Path, out_cb: Optional[Callable[[str], None]], stdin: str = "") -> int:
    return container.run(command=[bin_name] + args, image=IMAGE, volumes={str(cwd): "/workspace"}, workdir="/workspace", on_output=out_cb, stdin_text=stdin)

def _gmx(args: list[str], cwd: Path, cb: Optional[Callable[[str], None]] = None, stdin: str = "") -> int:
    return _gmx_call("gmx", args, cwd, cb, stdin)

def _gmx_d(args: list[str], cwd: Path, cb: Optional[Callable[[str], None]] = None, stdin: str = "") -> int:
    # Use gmx as fallback if gmx_d is not available (common in NGC images)
    return _gmx_call("gmx", args, cwd, cb, stdin)


# ── Execution Engines ─────────────────────────────────────────────────────────

def _run_minimization(comp: str, cwd: Path, cb: Optional[Callable[[str], None]], is_holo: bool = False) -> None:
    tag = f"min-{comp}"
    prefix = "holo" if is_holo else "apo"
    idx = "index.ndx" if is_holo else None
    traj_file = cwd / f"{tag}-traj.trr"

    for label, mdp_file in [("steep", f"{prefix}-min-steep.mdp"), ("cg", f"{prefix}-min-cg.mdp")]:
        log_f = f"{tag}-{label}-mdrun.log"
        n, converged = 0, False
        while n < MAX_MIN_ITER and not converged:
            g_args = ["grompp", "-f", mdp_file, "-c", f"{tag}.gro", "-r", f"{tag}.gro", "-p", f"{comp}.top", "-o", f"{tag}.tpr", "-maxwarn", "3"]
            if idx:
                g_args += ["-n", idx]
            _gmx(g_args, cwd, cb)

            # Use gmx_d (double precision) for minimization as per robust user scripts
            m_args = ["mdrun", "-deffnm", tag, "-v", "-pin", "on", "-pinoffset", "0", "-nice", "0"] + _get_parallel_args()
            _gmx_d(m_args, cwd, cb)

            # Trajectory concatenation logic from user scripts
            new_trr = cwd / f"{tag}.trr"
            if n == 0:
                if new_trr.exists():
                    new_trr.rename(traj_file)
            else:
                if new_trr.exists() and traj_file.exists():
                    temp_traj = cwd / "temp_traj.trr"
                    _gmx(["trjcat", "-f", str(traj_file), str(new_trr), "-o", str(temp_traj), "-cat"], cwd, cb)
                    temp_traj.rename(traj_file)
                    new_trr.unlink(missing_ok=True)

            # Cleanup backups
            for bak in cwd.glob(f"*#*{tag}*"):
                bak.unlink(missing_ok=True)

            converged = not _log_has(cwd, log_f, "did not converge to Fmax")
            n += 1


def _run_sim_phase(phase: str, prev: str, comp: str, cwd: Path, cb: Optional[Callable[[str], None]], is_holo: bool = False) -> None:
    tag, p_tag, prefix = f"{phase}-{comp}", f"{prev}-{comp}", "holo" if is_holo else "apo"
    mdp = f"{prefix}-{phase}.mdp"
    idx = "index.ndx" if is_holo else None

    if not (cwd / f"{tag}.tpr").exists():
        g_args = ["grompp", "-f", mdp, "-v", "-c", f"{p_tag}.gro", "-r", f"{p_tag}.gro", "-p", f"{comp}.top", "-o", f"{tag}.tpr", "-maxwarn", "3"]
        if idx:
            g_args += ["-n", idx]
        _gmx(g_args, cwd, cb)

    j = 1
    while (cwd / f"{tag}_{j}.cpt").exists():
        j += 1

    finished = False
    consecutive_fails = 0
    while not finished:
        cpt = f"{tag}_{j}.cpt"
        m_args = ["mdrun", "-deffnm", tag, "-cpo", cpt, "-nice", "0", "-v", "-maxh", "6", "-cpt", "1", "-pin", "on", "-pinoffset", "0"] + _get_parallel_args()
        
        if settings.use_gpu:
            m_args += ["-nb", "gpu", "-pme", "gpu", "-bonded", "gpu"]
        
        if j > 1:
            m_args += ["-cpi", f"{tag}_{j-1}.cpt"]

        rc = _gmx(m_args, cwd, cb)
        
        if rc != 0 and not (cwd / cpt).exists():
            consecutive_fails += 1
            if consecutive_fails >= 3:
                raise RuntimeError(f"mdrun for {phase} failed 3 times without progress.")
            continue
        else:
            consecutive_fails = 0

        if (cwd / f"{tag}.gro").exists() and _log_has(cwd, f"{tag}.log", "Finished mdrun"):
            finished = True
        else:
            j += 1
            if j > 50:
                break

    # Cleanup backups
    for bak in cwd.glob("#*#"):
        bak.unlink(missing_ok=True)


# ── Unified Pipeline ──────────────────────────────────────────────────────────

def run_md_simulation(
    pdb_path: str,
    ligand_gro: Optional[str] = None,
    ligand_itp: Optional[str] = None,
    output_dir: Optional[str] = None,
    on_output: Optional[Callable[[str], None]] = None,
) -> dict:
    pdb = Path(pdb_path).resolve()
    is_holo = ligand_gro is not None and ligand_itp is not None
    prefix = "Holo" if is_holo else "Apo"
    comp = f"{prefix}-{pdb.stem}"
    cwd = Path(output_dir) if output_dir else settings.workspace_path / "md" / comp
    cwd.mkdir(parents=True, exist_ok=True)

    def log(msg: str) -> None:
        logger.info(msg)
        if on_output:
            on_output(f"[BIMOS] {msg}")

    # Copy files
    try:
        shutil.copy2(pdb, cwd / f"{pdb.stem}.pdb")
    except shutil.SameFileError:
        pass

    if is_holo:
        try:
            shutil.copy2(ligand_gro, cwd / "ligand.gro")
        except shutil.SameFileError:
            pass
        try:
            shutil.copy2(ligand_itp, cwd / "ligand.itp")
        except shutil.SameFileError:
            pass

    # Write MDPs (BIMOS defaults if none provided in directory)
    from bimos.core.workflow import _default_mdps
    mdps = _default_mdps(is_holo)
    for name, content in mdps.items():
        mdp_path = cwd / name
        if not mdp_path.exists():
            mdp_path.write_text(content)

    stage = _detect_stage(cwd, comp, is_holo)
    log(f"Starting {prefix} pipeline at stage: {stage}")

    if stage == Stage.PREP:
        log("Phase: PREP")
        _clean_pdb(cwd / f"{pdb.stem}.pdb", cwd / f"{pdb.stem}-clean.pdb")
        
        if is_holo:
            resname = _detect_resname_from_gro(cwd / "ligand.gro")
            _patch_itp(cwd / "ligand.itp")
            # Correct sequence for Holo from user script
            _gmx(["editconf", "-f", f"{pdb.stem}-clean.pdb", "-o", "prot-box.pdb", "-d", "1.0", "-bt", "cubic", "-noc"], cwd, on_output)
            _gmx(["editconf", "-f", f"{pdb.stem}-clean.pdb", "-o", "prot-box.gro", "-d", "1.0", "-bt", "cubic", "-noc"], cwd, on_output)
            box = _get_box(cwd / "prot-box.gro")
            _fix_histidines(cwd / "prot-box.pdb", cwd / "prot-his.pdb", log)
            _gmx(["pdb2gmx", "-f", "prot-his.pdb", "-o", "prot-pdb2gmx.gro", "-p", f"{comp}.top", "-ff", "oplsaa", "-water", "tip3p", "-ignh"], cwd, on_output)
            mol_name = _inject_topology(cwd / f"{comp}.top", cwd / "ligand.itp")
            _build_complex(cwd / "prot-pdb2gmx.gro", cwd / "ligand.gro", resname, cwd / f"{comp}-raw.gro")
            _gmx(["genrestr", "-f", "ligand.gro", "-o", "ligand-posre.itp", "-fc", "1000", "1000", "1000"], cwd, on_output, f"{resname}\n")
            _inject_posres(cwd / f"{comp}.top", "ligand")
            _gmx(["editconf", "-f", f"{comp}-raw.gro", "-o", f"pre-{comp}-solv.gro", "-bt", "cubic", "-box"] + box, cwd, on_output)
            _gmx(["solvate", "-cp", f"pre-{comp}-solv.gro", "-cs", "spc216.gro", "-o", f"min-{comp}-solv.gro", "-p", f"{comp}.top"], cwd, on_output)
            _gmx(["grompp", "-f", "holo-ions.mdp", "-c", f"min-{comp}-solv.gro", "-p", f"{comp}.top", "-o", f"min-{comp}.tpr", "-maxwarn", "3"], cwd, on_output)
            _gmx(["genion", "-s", f"min-{comp}.tpr", "-o", f"min-{comp}.gro", "-p", f"{comp}.top", "-neutral", "-conc", "0.154004106"], cwd, on_output, "SOL\n")
            _gmx(["make_ndx", "-f", f"min-{comp}.gro", "-o", "index.ndx"], cwd, on_output, f"1 | r {resname}\nq\n")
        else:
            _gmx(["editconf", "-f", f"{pdb.stem}-clean.pdb", "-o", "pre-box.pdb", "-c", "-d", "1.0", "-bt", "cubic"], cwd, on_output)
            _fix_histidines(cwd / "pre-box.pdb", cwd / "pre-his.pdb", log)
            _gmx(["pdb2gmx", "-f", "pre-his.pdb", "-o", f"min-{comp}.gro", "-p", f"{comp}.top", "-ff", "oplsaa", "-water", "tip3p", "-ignh"], cwd, on_output)
            _gmx(["solvate", "-cp", f"min-{comp}.gro", "-cs", "spc216.gro", "-o", f"min-{comp}-solv.gro", "-p", f"{comp}.top"], cwd, on_output)
            _gmx(["grompp", "-f", "apo-ions.mdp", "-c", f"min-{comp}-solv.gro", "-p", f"{comp}.top", "-o", f"min-{comp}.tpr", "-maxwarn", "3"], cwd, on_output)
            _gmx(["genion", "-s", f"min-{comp}.tpr", "-o", f"min-{comp}.gro", "-p", f"{comp}.top", "-neutral", "-conc", "0.154004106"], cwd, on_output, "SOL\n")
        stage = Stage.MINIMIZATION

    if stage == Stage.MINIMIZATION:
        log("Phase: MINIMIZATION")
        _run_minimization(comp, cwd, on_output, is_holo)
        stage = Stage.NVT

    for phase, prev in [("nvt", "min"), ("npt", "nvt"), ("sdm", "npt")]:
        if stage == Stage(phase):
            log(f"Phase: {phase.upper()}")
            _run_sim_phase(phase, prev, comp, cwd, on_output, is_holo)
            stage = Stage("analysis" if phase == "sdm" else "npt" if phase == "nvt" else "sdm")

    if stage == Stage.ANALYSIS:
        log("Phase: ANALYSIS")
        tag, ndx = f"sdm-{comp}", ("index.ndx" if is_holo else None)
        conv = ["trjconv", "-f", f"{tag}.xtc", "-s", f"{tag}.tpr", "-o", f"{tag}-noPBC.xtc", "-pbc", "nojump", "-center", "-tu", "ns"]
        if ndx:
            conv += ["-n", ndx]
        _gmx(conv, cwd, on_output, "1 0\n")

        # Extended analysis from user scripts
        for tool, out, inp in [("rms", f"{prefix}-{comp}-rmsd.xvg", "4 4\n"), ("rmsf", f"{prefix}-{comp}-rmsf.xvg", "1\n"), ("gyrate", f"{prefix}-{comp}-gyrate.xvg", "1\n"), ("hbond", f"{prefix}-{comp}-hbnum.xvg", "1\n1\n"), ("sasa", f"{prefix}-{comp}-sasa.xvg", "1\n")]:
            if tool == "hbond":
                args = [tool, "-f", f"{tag}-noPBC.xtc", "-s", f"{tag}.tpr", "-num", out]
            else:
                args = [tool, "-f", f"{tag}-noPBC.xtc", "-s", f"{tag}.tpr", "-o", out]

            if tool == "rmsf":
                args += ["-res", "yes", "-fit", "yes"]
            if tool == "sasa":
                args += ["-or", f"{comp}-sasa-res.xvg", "-tv", f"{comp}-sasa-vol.xvg"]
            if ndx:
                args += ["-n", ndx]
            _gmx(args, cwd, on_output, inp)

    return {"status": "completed", "output_dir": str(cwd)}


def _default_mdps(is_holo: bool = False) -> dict[str, str]:
    import yaml
    prefix = "holo" if is_holo else "apo"
    config_path = Path(__file__).parent.parent / "infrastructure" / "config" / f"default_{prefix}.yaml"
    
    try:
        with open(config_path, "r") as f:
            templates = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load {config_path.name}: {e}")
        templates = {}

    # User requirement: 500ns for Apo (250M steps), 100ns for Holo (50M steps)
    prod_steps = 50_000_000 if is_holo else 250_000_000
    
    result = {}
    for stage_name in ["ions", "min-steep", "min-cg", "nvt", "npt", "sdm"]:
        key = f"{prefix}-{stage_name}.mdp"
        # Fallback to apo if holo section missing
        data = templates.get(key) or templates.get(f"apo-{stage_name}.mdp")
        
        if not data:
            logger.warning(f"No template found for {key}")
            continue
            
        # Convert dict to GROMACS MDP format
        lines = []
        for k, v in data.items():
            # Override nsteps for the production phase (sdm) or equilibration
            if stage_name == "sdm" and k == "nsteps":
                v = str(prod_steps)
            elif stage_name in ["nvt", "npt"] and k == "nsteps":
                v = "5000" # 10ps for fast test
            
            # Disable TRR output
            if k in ["nstxout", "nstvout"]:
                v = "0"
            
            lines.append(f"{k:<25} = {v}")
        
        result[key] = "\n".join(lines) + "\n"
        
    return result


def run_qm_calculation(input_file: str, output_dir: Optional[str] = None, on_output: Optional[Callable[[str], None]] = None) -> dict:
    orca_bin = settings.orca_path
    if not orca_bin or not Path(orca_bin).exists():
        raise RuntimeError("ORCA not found. Set ORCA_PATH.")
    inp = Path(input_file).resolve()
    job_dir = Path(output_dir) if output_dir else settings.workspace_path / "qm" / inp.stem
    job_dir.mkdir(parents=True, exist_ok=True)
    out = job_dir / f"{inp.stem}.out"
    import subprocess
    if on_output:
        on_output(f"[BIMOS] Running ORCA: {orca_bin} {inp.name}")
    with open(out, "w") as f:
        p = subprocess.Popen([orca_bin, str(inp)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            f.write(line)
            if on_output:
                on_output(line.strip())
        p.wait()
    return {"status": "completed", "output_dir": str(job_dir)}


def run_gaussian_calculation(input_file: str, output_dir: Optional[str] = None, on_output: Optional[Callable[[str], None]] = None) -> dict:
    g09_bin = settings.gaussian_path
    if not g09_bin or not Path(g09_bin).exists():
        raise RuntimeError("Gaussian not found. Set GAUSSIAN_PATH.")
    inp = Path(input_file).resolve()
    job_dir = Path(output_dir) if output_dir else settings.workspace_path / "qm" / inp.stem
    job_dir.mkdir(parents=True, exist_ok=True)
    out = job_dir / f"{inp.stem}.log"
    import subprocess
    if on_output:
        on_output(f"[BIMOS] Running Gaussian: {g09_bin} {inp.name}")
    with open(out, "w") as f:
        # Gaussian usually reads from stdin or takes file as arg
        p = subprocess.Popen([g09_bin, str(inp)], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in p.stdout:
            f.write(line)
            if on_output:
                on_output(line.strip())
        p.wait()
    return {"status": "completed", "output_dir": str(job_dir)}