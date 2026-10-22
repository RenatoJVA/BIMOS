"""
GROMACS molecular dynamics pipeline for Apo and Holo systems.
"""

from __future__ import annotations

import logging
import re
import shutil
from collections import defaultdict
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any, ClassVar

import yaml

from bimos.config.settings import settings
from bimos.infrastructure import container
from bimos.molecular_dynamics.config import MDConfig
from bimos.shared.ligand_identity import (
    detect_gro_resname,
    gro_atom_lines,
    normalize_gro_resname,
    resolve_ligand_identity,
)
from bimos.shared.paths import INFRA_CONFIG_DIR
from bimos.shared.pipeline import Pipeline

logger = logging.getLogger("bimos.molecular_dynamics")

class Stage(StrEnum):
    PREP         = "prep"
    MINIMIZATION = "minimization"
    NVT          = "nvt"
    NPT          = "npt"
    SDM          = "sdm"
    ANALYSIS     = "analysis"
    DONE         = "done"

class MolecularDynamicsPipeline(Pipeline):
    """GROMACS molecular dynamics simulation pipeline."""

    workspace_subdir = "md"

    def __init__(
        self,
        output_dir: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        max_mode: bool | None = None,
    ) -> None:
        super().__init__(output_dir, on_output)
        self.md_config = MDConfig.resolve(max_mode=max_mode)

    def _get_parallel_args(self) -> list[str]:
        threads = settings.get_threads()
        return ["-ntmpi", "1", "-ntomp", str(threads)]

    def _gmx(self, args: list[str], cwd: Path, stdin: str = "") -> int:
        return container.run(
            command=["gmx", *args],
            image=settings.bimos_image,
            volumes={str(cwd): "/workspace"},
            workdir="/workspace",
            on_output=self.on_output,
            stdin_text=stdin
        )

    @staticmethod
    def _log_contains(cwd: Path, log_name: str, token: str) -> bool:
        log_path = cwd / log_name
        if not log_path.exists():
            return False
        try:
            with open(log_path, errors="replace") as f:
                for chunk in iter(lambda: f.read(8192), ""):
                    if token in chunk:
                        return True
            return False
        except OSError:
            return False

    def _detect_stage(self, cwd: Path, comp: str, is_holo: bool) -> Stage:
        prefix = "Holo" if is_holo else "Apo"
        if not (cwd / f"min-{comp}.gro").exists() or not (cwd / f"{comp}.top").exists():
            return Stage.PREP

        for label in ("steep", "cg"):
            log_name = f"min-{comp}-{label}-mdrun.log"
            if not (cwd / log_name).exists() or self._log_contains(
                cwd, log_name, "did not converge to Fmax"
            ):
                return Stage.MINIMIZATION

        for phase in ["nvt", "npt", "sdm"]:
            if not (cwd / f"{phase}-{comp}.gro").exists() or not self._log_contains(cwd, f"{phase}-{comp}.log", "Finished mdrun"):
                return Stage(phase)

        if not (cwd / f"{prefix}-{comp}-rmsd.xvg").exists():
            return Stage.ANALYSIS

        return Stage.DONE

    EXCLUDED_RESIDUES: ClassVar[set[str]] = {"HOH", "WAT", "NA", "CL", "K", "MG", "CA"}

    def _clean_pdb(self, input_pdb: Path, output_pdb: Path) -> None:
        with open(input_pdb) as fin, open(output_pdb, "w") as fout:
            for line in fin:
                if len(line) < 20:
                    fout.write(line)
                    continue
                record_type = line[0:6].strip()
                if record_type not in ("ATOM", "HETATM"):
                    continue
                res_name = line[17:20].strip()
                if res_name in self.EXCLUDED_RESIDUES:
                    continue
                fout.write(line)

    def _fix_histidines(self, input_pdb: Path, output_pdb: Path) -> None:
        def classify(atom_lines: list[str]) -> str:
            names = {ln[12:16].strip() for ln in atom_lines if ln.startswith(("ATOM", "HETATM"))}
            if any("HEME" in n for n in names):
                return "HIS1"
            if "HD1" in names and "HE2" in names:
                return "HISH"
            if "HD1" in names:
                return "HISD"
            if "HE2" in names:
                return "HISE"
            return "HISD"

        lines = input_pdb.read_text(errors="replace").splitlines(keepends=True)
        groups = defaultdict(list)
        for ln in lines:
            if ln.startswith(("ATOM", "HETATM")) and ln[17:20].strip() == "HIS":
                groups[(ln[21], ln[22:26].strip())].append(ln)

        types = {k: classify(v) for k, v in groups.items()}
        corrected = []
        for ln in lines:
            if ln.startswith(("ATOM", "HETATM")) and ln[17:20].strip() == "HIS":
                key = (ln[21], ln[22:26].strip())
                new = types.get(key, "HISD")
                self.log(f"Fixing His {key[0]}{key[1]}: HIS -> {new}")
                ln = ln[:17] + new.ljust(4)[:4] + ln[21:]
            corrected.append(ln)
        output_pdb.write_text("".join(corrected))

    def _run_minimization(self, comp: str, cwd: Path, is_holo: bool) -> None:
        tag = f"min-{comp}"
        prefix = "holo" if is_holo else "apo"
        idx = "index.ndx" if is_holo else None
        traj_file = cwd / f"{tag}-traj.trr"

        for label, mdp in [("steep", f"{prefix}-min-steep.mdp"), ("cg", f"{prefix}-min-cg.mdp")]:
            log_f = f"{tag}-{label}-mdrun.log"
            n, converged = 0, False
            while n < self.md_config.max_min_iterations and not converged:
                g_args = ["grompp", "-f", mdp, "-c", f"{tag}.gro", "-r", f"{tag}.gro", "-p", f"{comp}.top", "-o", f"{tag}.tpr", "-maxwarn", "3"]
                if idx:
                    g_args += ["-n", idx]
                rc = self._gmx(g_args, cwd)
                if rc != 0:
                    raise RuntimeError(f"grompp failed for {label} minimization of {comp} (exit {rc}).")

                m_args = ["mdrun", "-deffnm", tag, "-g", log_f, "-v", "-pin", "on", "-pinoffset", "0", "-nice", "0", *self._get_parallel_args()]
                rc = self._gmx(m_args, cwd)
                if rc != 0:
                    raise RuntimeError(f"mdrun failed for {label} minimization of {comp} (exit {rc}).")

                new_trr = cwd / f"{tag}.trr"
                if new_trr.exists():
                    if not traj_file.exists():
                        new_trr.rename(traj_file)
                    else:
                        temp = cwd / "temp_traj.trr"
                        rc = self._gmx(
                            [
                                "trjcat", "-f", traj_file.name, new_trr.name,
                                "-o", temp.name, "-cat",
                            ],
                            cwd,
                        )
                        if rc != 0:
                            raise RuntimeError(f"trjcat failed while minimizing {comp} (exit {rc}).")
                        temp.rename(traj_file)
                        new_trr.unlink(missing_ok=True)

                for bak in cwd.glob(f"*#*{tag}*"):
                    bak.unlink(missing_ok=True)
                if not (cwd / log_f).exists():
                    raise RuntimeError(f"mdrun produced no minimization log: {log_f}")
                converged = not self._log_contains(cwd, log_f, "did not converge to Fmax")
                n += 1

            if not converged:
                raise RuntimeError(
                    f"{label} minimization of {comp} did not converge after "
                    f"{self.md_config.max_min_iterations} iterations."
                )

    def _run_sim_phase(self, phase: str, prev: str, comp: str, cwd: Path, is_holo: bool) -> None:
        tag, p_tag, prefix = f"{phase}-{comp}", f"{prev}-{comp}", "holo" if is_holo else "apo"
        mdp, idx = f"{prefix}-{phase}.mdp", ("index.ndx" if is_holo else None)

        if not (cwd / f"{tag}.tpr").exists():
            g_args = ["grompp", "-f", mdp, "-v", "-c", f"{p_tag}.gro", "-r", f"{p_tag}.gro", "-p", f"{comp}.top", "-o", f"{tag}.tpr", "-maxwarn", "3"]
            if idx:
                g_args += ["-n", idx]
            self._gmx(g_args, cwd)

        j = 1
        while (cwd / f"{tag}_{j}.cpt").exists():
            j += 1

        finished, fails = False, 0
        while not finished:
            cpt = f"{tag}_{j}.cpt"
            m_args = ["mdrun", "-deffnm", tag, "-cpo", cpt, "-nice", "0", "-v", "-maxh", "6", "-cpt", "1", "-pin", "on", "-pinoffset", "0", *self._get_parallel_args()]
            if settings.use_gpu:
                m_args += ["-nb", "gpu", "-pme", "gpu", "-bonded", "gpu"]
            if j > 1:
                m_args += ["-cpi", f"{tag}_{j-1}.cpt"]

            rc = self._gmx(m_args, cwd)
            if rc != 0 and not (cwd / cpt).exists():
                fails += 1
                if fails >= 3:
                    raise RuntimeError(f"mdrun for {phase} failed 3 times.")
                continue
            else:
                fails = 0

            if (cwd / f"{tag}.gro").exists() and self._log_contains(cwd, f"{tag}.log", "Finished mdrun"):
                finished = True
            else:
                j += 1
                if j > 50:
                    break
        for bak in cwd.glob("#*#"):
            bak.unlink(missing_ok=True)

    def run(  # type: ignore[override]
        self,
        pdb_path: str,
        ligand_gro: str | None = None,
        ligand_itp: str | None = None,
    ) -> dict[str, Any]:
        pdb = Path(pdb_path).resolve()
        is_holo = ligand_gro is not None and ligand_itp is not None
        prefix = "Holo" if is_holo else "Apo"

        # Dual ligand identity: candidate (filename stem) names the output,
        # internal resname/moleculetype (UNK/LIG/...) drives GROMACS ops.
        candidate = ""
        internal = ""
        if is_holo:
            if ligand_gro is None or ligand_itp is None:
                raise ValueError("Holo pipeline requires both ligand_gro and ligand_itp")
            identity = resolve_ligand_identity(Path(ligand_gro), Path(ligand_itp))
            candidate = identity.candidate
            internal = identity.itp_moleculetype
            for warning in identity.warnings:
                self.log(f"Ligand '{candidate}': {warning}")
            self.log(
                f"Ligand '{candidate}' (candidate) -> internal '{internal}' "
                f"(gro={identity.gro_resname}, itp={identity.itp_moleculetype})"
            )

        comp = f"{prefix}-{pdb.stem}-{candidate}" if is_holo else f"{prefix}-{pdb.stem}"

        # Override output_dir with job-specific one
        cwd = self.output_dir / comp
        cwd.mkdir(parents=True, exist_ok=True)

        shutil.copy2(pdb, cwd / f"{pdb.stem}.pdb")
        lig_gro_name = f"{candidate}.gro" if is_holo else ""
        lig_itp_name = f"{candidate}.itp" if is_holo else ""
        lig_posre_name = f"{candidate}-posre.itp" if is_holo else ""
        if is_holo:
            if ligand_gro is None or ligand_itp is None:
                raise ValueError("Holo pipeline requires both ligand_gro and ligand_itp")
            if identity.needs_gro_normalization:
                n = normalize_gro_resname(Path(ligand_gro), cwd / lig_gro_name, internal)
                self.log(f"Normalized {n} .gro lines to internal resname '{internal}'")
            else:
                shutil.copy2(ligand_gro, cwd / lig_gro_name)
            shutil.copy2(ligand_itp, cwd / lig_itp_name)

        mdps = self._default_mdps(is_holo)
        for name, content in mdps.items():
            mdp_path = cwd / name
            if not mdp_path.exists():
                mdp_path.write_text(content)

        stage = self._detect_stage(cwd, comp, is_holo)
        self.log(f"Starting {prefix} pipeline at stage: {stage} (profile={self.md_config.profile})")

        if stage == Stage.PREP:
            self.log("Phase: PREP")
            self._clean_pdb(cwd / f"{pdb.stem}.pdb", cwd / f"{pdb.stem}-clean.pdb")
            if is_holo:
                resname = internal
                self._patch_itp(cwd / lig_itp_name)
                self._gmx(["editconf", "-f", f"{pdb.stem}-clean.pdb", "-o", "prot-box.pdb", "-d", self.md_config.box_distance, "-bt", "cubic", "-noc"], cwd)
                self._gmx(["editconf", "-f", f"{pdb.stem}-clean.pdb", "-o", "prot-box.gro", "-d", self.md_config.box_distance, "-bt", "cubic", "-noc"], cwd)
                box = self._get_box(cwd / "prot-box.gro")
                self._fix_histidines(cwd / "prot-box.pdb", cwd / "prot-his.pdb")
                self._gmx(["pdb2gmx", "-f", "prot-his.pdb", "-o", "prot-pdb2gmx.gro", "-p", f"{comp}.top", "-ff", self.md_config.forcefield, "-water", self.md_config.water_model, "-ignh"], cwd)
                self._inject_topology(cwd / f"{comp}.top", cwd / lig_itp_name)
                self._build_complex(cwd / "prot-pdb2gmx.gro", cwd / lig_gro_name, resname, cwd / f"{comp}-raw.gro")
                self._gmx(["genrestr", "-f", lig_gro_name, "-o", lig_posre_name, "-fc", "1000", "1000", "1000"], cwd, f"{resname}\n")
                self._inject_posres(cwd / f"{comp}.top", candidate)
                self._gmx(["editconf", "-f", f"{comp}-raw.gro", "-o", f"pre-{comp}-solv.gro", "-bt", "cubic", "-box", *box], cwd)
                self._gmx(["solvate", "-cp", f"pre-{comp}-solv.gro", "-cs", self.md_config.solvent_gro, "-o", f"min-{comp}-solv.gro", "-p", f"{comp}.top"], cwd)
                self._gmx(["grompp", "-f", "holo-ions.mdp", "-c", f"min-{comp}-solv.gro", "-p", f"{comp}.top", "-o", f"min-{comp}.tpr", "-maxwarn", "3"], cwd)
                self._gmx(["genion", "-s", f"min-{comp}.tpr", "-o", f"min-{comp}.gro", "-p", f"{comp}.top", "-neutral", "-conc", self.md_config.ion_concentration], cwd, "SOL\n")
                self._gmx(["make_ndx", "-f", f"min-{comp}.gro", "-o", "index.ndx"], cwd, f"1 | r {resname}\nq\n")
            else:
                self._gmx(["editconf", "-f", f"{pdb.stem}-clean.pdb", "-o", "pre-box.pdb", "-c", "-d", self.md_config.box_distance, "-bt", "cubic"], cwd)
                self._fix_histidines(cwd / "pre-box.pdb", cwd / "pre-his.pdb")
                self._gmx(["pdb2gmx", "-f", "pre-his.pdb", "-o", f"min-{comp}.gro", "-p", f"{comp}.top", "-ff", self.md_config.forcefield, "-water", self.md_config.water_model, "-ignh"], cwd)
                self._gmx(["solvate", "-cp", f"min-{comp}.gro", "-cs", self.md_config.solvent_gro, "-o", f"min-{comp}-solv.gro", "-p", f"{comp}.top"], cwd)
                self._gmx(["grompp", "-f", "apo-ions.mdp", "-c", f"min-{comp}-solv.gro", "-p", f"{comp}.top", "-o", f"min-{comp}.tpr", "-maxwarn", "3"], cwd)
                self._gmx(["genion", "-s", f"min-{comp}.tpr", "-o", f"min-{comp}.gro", "-p", f"{comp}.top", "-neutral", "-conc", self.md_config.ion_concentration], cwd, "SOL\n")
            stage = Stage.MINIMIZATION

        if stage == Stage.MINIMIZATION:
            self.log("Phase: MINIMIZATION")
            self._run_minimization(comp, cwd, is_holo)
            stage = Stage.NVT

        for phase, prev in [("nvt", "min"), ("npt", "nvt"), ("sdm", "npt")]:
            if stage == Stage(phase):
                self.log(f"Phase: {phase.upper()}")
                self._run_sim_phase(phase, prev, comp, cwd, is_holo)
                stage = Stage("analysis" if phase == "sdm" else "npt" if phase == "nvt" else "sdm")

        if stage == Stage.ANALYSIS:
            self.log("Phase: ANALYSIS")
            tag, ndx = f"sdm-{comp}", ("index.ndx" if is_holo else None)
            conv = ["trjconv", "-f", f"{tag}.xtc", "-s", f"{tag}.tpr", "-o", f"{tag}-noPBC.xtc", "-pbc", "nojump", "-center", "-tu", "ns"]
            if ndx:
                conv += ["-n", ndx]
            self._gmx(conv, cwd, "1 0\n")

            for tool, out, inp in [("rms", f"{prefix}-{comp}-rmsd.xvg", "4 4\n"), ("rmsf", f"{prefix}-{comp}-rmsf.xvg", "1\n"), ("gyrate", f"{prefix}-{comp}-gyrate.xvg", "1\n"), ("hbond", f"{prefix}-{comp}-hbnum.xvg", "1\n1\n"), ("sasa", f"{prefix}-{comp}-sasa.xvg", "1\n")]:
                args = [tool, "-f", f"{tag}-noPBC.xtc", "-s", f"{tag}.tpr", ("-num" if tool == "hbond" else "-o"), out]
                if tool == "rmsf":
                    args += ["-res", "yes", "-fit", "yes"]
                if tool == "sasa":
                    args += ["-or", f"{comp}-sasa-res.xvg", "-tv", f"{comp}-sasa-vol.xvg"]
                if ndx:
                    args += ["-n", ndx]
                self._gmx(args, cwd, inp)

        result: dict[str, Any] = {"status": "completed", "output_dir": str(cwd), "comp": comp}
        if is_holo:
            result["candidate"] = candidate
            result["ligand_internal"] = internal
        return result

    def run_batch(
        self,
        protein_dir: str | Path,
        ligand_dir: str | Path,
        collect_graphs: bool = True,
    ) -> list[dict[str, Any]]:
        """Run Holo MD for every protein x ligand pair (like Holo_.py).

        Proteins are ``*.pdb`` in *protein_dir*; ligands are ``*.gro`` + ``*.itp``
        pairs matched by stem in *ligand_dir*. Each pair runs :meth:`run` and
        lands in ``{output_dir}/Holo-{PROT}-{LIG}/``. With *collect_graphs*,
        every ``*.xvg`` is also copied to ``{output_dir}/Analysis_graphs-Holo/``.
        """
        from itertools import product

        prot_dir = Path(protein_dir)
        lig_dir = Path(ligand_dir)
        pdb_files = sorted(prot_dir.glob("*.pdb"))
        if not pdb_files:
            raise ValueError(f"No .pdb files found in {prot_dir}")
        lig_gros = {p.stem: p for p in lig_dir.glob("*.gro")}
        lig_itps = {p.stem: p for p in lig_dir.glob("*.itp")}
        ligands = sorted(set(lig_gros) & set(lig_itps))
        if not ligands:
            raise ValueError(f"No matching .gro+.itp pairs found in {lig_dir}")
        self.log(f"Proteins: {[p.stem for p in pdb_files]}")
        self.log(f"Ligands: {ligands}")

        results: list[dict[str, Any]] = []
        for pdb_path, lig_name in product(pdb_files, ligands):
            self.log(f"Processing: {lig_name}-{pdb_path.stem}")
            results.append(
                self.run(
                    pdb_path=str(pdb_path),
                    ligand_gro=str(lig_gros[lig_name]),
                    ligand_itp=str(lig_itps[lig_name]),
                )
            )

        if collect_graphs:
            graphs_dir = self.output_dir / "Analysis_graphs-Holo"
            graphs_dir.mkdir(parents=True, exist_ok=True)
            for res in results:
                for xvg in Path(res["output_dir"]).glob("*.xvg"):
                    shutil.copy2(xvg, graphs_dir / xvg.name)
        return results

    def _detect_resname(self, gro: Path) -> str:
        return detect_gro_resname(gro)

    def _patch_itp(self, itp: Path) -> None:
        lines = itp.read_text(errors="replace").splitlines(keepends=True)
        in_block, patched = False, []
        for ln in lines:
            if ln.startswith(";---"):
                in_block = True
            if in_block:
                if not ln.startswith(";"):
                    ln = ";" + ln
                if re.match(r"^\s*[0-9]", ln.lstrip(";")):
                    in_block = False
            patched.append(ln)
        itp.write_text("".join(patched))

    def _inject_topology(self, top: Path, itp: Path) -> None:
        content = itp.read_text(errors="replace")
        m = re.search(r"\[\s*moleculetype\s*\]\s*\n\s*;?[^\n]*\n\s*(\S+)", content, re.MULTILINE)
        name = m.group(1) if m else "ligand"
        t_content = top.read_text(errors="replace")
        inc = f'#include "{itp.name}"'
        if inc not in t_content:
            t_content = re.sub(r"(#include\s+\"[^\"]*forcefield\.itp\")", r"\1\n" + inc, t_content, count=1)
        if name not in t_content.split("[ molecules ]")[-1]:
            t_content = t_content.rstrip() + f"\n{name:<20}1\n"
        top.write_text(t_content)

    def _inject_posres(self, top: Path, name: str) -> None:
        content = top.read_text(errors="replace")
        if "POSRES_LIG" not in content:
            block = f"; Strong restraints\n#ifdef POSRES_LIG\n#include \"{name}-posre.itp\"\n#endif\n\n"
            marker = "; Include water topology"
            content = content.replace(marker, block + marker, 1) if marker in content else content.rstrip() + "\n" + block
            top.write_text(content)

    def _build_complex(self, prot: Path, lig: Path, res: str, out: Path) -> None:
        p_lines = prot.read_text().splitlines(keepends=True)
        l_lines = gro_atom_lines(lig, res)
        n = len(p_lines) - 3 + len(l_lines)
        new = [p_lines[0], f" {n}\n", *p_lines[2:-1], *l_lines, p_lines[-1]]
        out.write_text("".join(new))

    def _get_box(self, gro: Path) -> list[str]:
        return gro.read_text().splitlines()[-1].split()[:3]

    def _default_mdps(self, is_holo: bool) -> dict[str, str]:
        prefix = "holo" if is_holo else "apo"
        path = INFRA_CONFIG_DIR / f"default_{prefix}.yaml"
        templates: dict[str, Any] = {}
        if path.exists():
            with open(path, encoding="utf-8") as handle:
                templates = yaml.safe_load(handle) or {}

        sdm_steps = self.md_config.sdm_steps_holo if is_holo else self.md_config.sdm_steps_apo
        result: dict[str, str] = {}
        for stage in ["ions", "min-steep", "min-cg", "nvt", "npt", "sdm"]:
            key = f"{prefix}-{stage}.mdp"
            data = templates.get(key) or templates.get(f"apo-{stage}.mdp")
            if not data:
                continue
            lines = []
            for param, value in data.items():
                if stage == "sdm" and param == "nsteps":
                    value = str(sdm_steps)
                elif stage in ("nvt", "npt") and param == "nsteps":
                    value = str(self.md_config.nvt_npt_steps)
                if param in ("nstxout", "nstvout"):
                    value = "0"
                lines.append(f"{param:<25} = {value}")
            result[key] = "\n".join(lines) + "\n"
        return result


def run_md_simulation(**kwargs: Any) -> dict[str, Any] | list[dict[str, Any]]:
    output_dir = kwargs.pop("output_dir", None)
    on_output = kwargs.pop("on_output", None)
    max_mode = kwargs.pop("max_resources", None)
    pipeline = MolecularDynamicsPipeline(
        output_dir=output_dir,
        on_output=on_output,
        max_mode=max_mode,
    )
    if "protein_dir" in kwargs or "ligand_dir" in kwargs:
        protein_dir = kwargs.pop("protein_dir", None)
        ligand_dir = kwargs.pop("ligand_dir", None)
        if not protein_dir or not ligand_dir:
            raise ValueError("Batch mode requires both protein_dir and ligand_dir")
        return pipeline.run_batch(protein_dir=protein_dir, ligand_dir=ligand_dir)
    return pipeline.run(**kwargs)
