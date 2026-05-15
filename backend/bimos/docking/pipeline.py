"""
Molecular docking pipeline using AutoDock Vina.
"""

from __future__ import annotations

import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from bimos.config.settings import settings
from bimos.docking.config import DockingConfig
from bimos.docking.sdf import split_multi_molecule_sdf
from bimos.infrastructure import container
from bimos.shared.paths import SCRIPTS_DIR
from bimos.shared.pipeline import Pipeline
from bimos.shared.templates import render_template

logger = logging.getLogger("bimos.docking")

VINA_TEMPLATE = Path(__file__).parent / "templates" / "vina.conf.template"


class DockingPipeline(Pipeline):
    """Automated pipeline for molecular docking with AutoDock Vina."""

    workspace_subdir = "docking"

    def __init__(
        self,
        output_dir: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        max_mode: bool | None = None,
        **vina_overrides: Any,
    ) -> None:
        super().__init__(output_dir, on_output)
        self.config = DockingConfig.resolve(max_mode=max_mode, **vina_overrides)

        self.proteins_dir = self.output_dir / "proteins"
        self.ligands_dir = self.output_dir / "ligands"
        self.results_dir = self.output_dir / "results"
        self.bests_dir = self.results_dir / "bests"
        for directory in (self.proteins_dir, self.ligands_dir, self.results_dir, self.bests_dir):
            directory.mkdir(parents=True, exist_ok=True)

    def _container_run(self, cmd: list[str], work_dir: Path) -> int:
        return container.run(
            command=cmd,
            image=settings.bimos_image,
            volumes={str(work_dir): "/work", str(SCRIPTS_DIR): "/scripts"},
            workdir="/work",
            on_output=self.on_output,
        )

    @staticmethod
    def _read_coords(pdbqt_path: Path) -> tuple[list[float], list[float], list[float]]:
        xs, ys, zs = [], [], []
        with open(pdbqt_path, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith(("ATOM", "HETATM")):
                    try:
                        xs.append(float(line[30:38]))
                        ys.append(float(line[38:46]))
                        zs.append(float(line[46:54]))
                    except ValueError:
                        continue
        return xs, ys, zs

    def _write_grid_box_conf(self, pdbqt_path: Path, conf_path: Path) -> None:
        if self.config.grid_mode == "manual":
            required = (
                self.config.center_x,
                self.config.center_y,
                self.config.center_z,
                self.config.size_x,
                self.config.size_y,
                self.config.size_z,
            )
            if any(value is None for value in required):
                raise ValueError(
                    "grid.mode is 'manual' but center/size coordinates are missing in docking.yaml"
                )
            cx, cy, cz = (round(v, 3) for v in required[:3])  # type: ignore[arg-type]
            sx, sy, sz = (round(v, 3) for v in required[3:])  # type: ignore[arg-type]
        else:
            xs, ys, zs = self._read_coords(pdbqt_path)
            if not xs:
                raise ValueError(f"No ATOM/HETATM coordinates found in {pdbqt_path}")
            cx, cy, cz = [round(sum(values) / len(values), 3) for values in (xs, ys, zs)]
            sx, sy, sz = [
                round(max(values) - min(values) + self.config.margin, 3)
                for values in (xs, ys, zs)
            ]
        conf_path.write_text(
            render_template(
                VINA_TEMPLATE,
                center_x=cx,
                center_y=cy,
                center_z=cz,
                size_x=sx,
                size_y=sy,
                size_z=sz,
                num_modes=self.config.num_modes,
                energy_range=self.config.energy_range,
                exhaustiveness=self.config.exhaustiveness,
            ),
            encoding="utf-8",
        )

    def _prepare_receptor(self, pdb_path: Path) -> Path:
        pdbqt_path = pdb_path.with_suffix(".pdbqt")
        if pdbqt_path.exists():
            return pdbqt_path

        rc = self._container_run(
            ["mk_prepare_receptor.py", "--read_pdb", pdb_path.name, "-p", pdbqt_path.name],
            work_dir=pdb_path.parent,
        )
        if rc != 0 or not pdbqt_path.exists():
            raise RuntimeError(f"Receptor preparation failed for {pdb_path.name} (exit {rc})")
        return pdbqt_path

    def _prepare_ligand(self, sdf_path: Path) -> Path | None:
        pdbqt_path = sdf_path.with_suffix(".pdbqt")
        if pdbqt_path.exists():
            return pdbqt_path

        sdf_h = sdf_path.with_name(f"{sdf_path.stem}_h.sdf")
        try:
            rc = self._container_run(
                [
                    "python3",
                    "/scripts/prepare_ligand.py",
                    "--input",
                    sdf_path.name,
                    "--output",
                    sdf_h.name,
                ],
                work_dir=sdf_path.parent,
            )
            if rc != 0:
                logger.warning("RDKit preparation failed for %s", sdf_path.name)
                return None

            rc = self._container_run(
                [
                    "mk_prepare_ligand.py",
                    "-i",
                    sdf_h.name,
                    "-o",
                    pdbqt_path.name,
                    "--charge_model",
                    "gasteiger",
                    "--rename_atoms",
                ],
                work_dir=sdf_path.parent,
            )
            if rc != 0 or not pdbqt_path.exists():
                logger.warning("Meeko preparation failed for %s", sdf_path.name)
                return None
        finally:
            sdf_h.unlink(missing_ok=True)
        return pdbqt_path

    @staticmethod
    def _extract_best_score(pdbqt_file: Path) -> float | None:
        with open(pdbqt_file, encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("REMARK VINA RESULT:"):
                    try:
                        return float(line.split()[3])
                    except (IndexError, ValueError):
                        continue
        return None

    def run(self, protein_pdb: str, ligands_sdf: str) -> dict[str, Any]:
        protein_path = Path(protein_pdb).resolve()
        ligands_path = Path(ligands_sdf).resolve()
        if not protein_path.exists():
            raise FileNotFoundError(f"Receptor PDB not found: {protein_path}")
        if not ligands_path.exists():
            raise FileNotFoundError(f"Ligands SDF not found: {ligands_path}")

        pdb_dest = self.proteins_dir / protein_path.name
        shutil.copy2(protein_path, pdb_dest)
        shutil.copy2(ligands_path, self.ligands_dir / "ligands.sdf")

        self.log("Step 1: Preparing receptor...")
        receptor_pdbqt = self._prepare_receptor(pdb_dest)

        self.log("Step 2: Splitting ligand SDF...")
        sdf_files = split_multi_molecule_sdf(self.ligands_dir / "ligands.sdf", self.ligands_dir)
        if not sdf_files:
            raise RuntimeError("No molecules found in the SDF file.")

        self.log(f"Step 3: Preparing {len(sdf_files)} ligand(s)...")
        ligand_pdbqts: list[Path] = []
        for sdf in sdf_files:
            pdbqt = self._prepare_ligand(sdf)
            if pdbqt:
                ligand_pdbqts.append(pdbqt)
            else:
                self.log(f"Skipping ligand {sdf.name} (preparation failed)", logging.WARNING)
        if not ligand_pdbqts:
            raise RuntimeError("No ligands prepared successfully.")

        self.log(
            f"Step 4: Docking {len(ligand_pdbqts)} ligand(s) "
            f"(times={self.config.times}, profile={self.config.profile})..."
        )
        conf_path = self.proteins_dir / f"{protein_path.stem}.conf"
        self._write_grid_box_conf(receptor_pdbqt, conf_path)

        final_results: list[dict[str, Any]] = []
        for lig_pdbqt in ligand_pdbqts:
            complex_name = f"{protein_path.stem}-{lig_pdbqt.stem}"
            complex_dir = self.results_dir / complex_name
            complex_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(receptor_pdbqt, complex_dir / receptor_pdbqt.name)
            shutil.copy2(lig_pdbqt, complex_dir / lig_pdbqt.name)
            shutil.copy2(conf_path, complex_dir / conf_path.name)

            def _run_single_vina(run_index: int) -> tuple[int, Path, float | None]:
                out_name = f"{complex_name}-{run_index}.pdbqt"
                rc = self._container_run(
                    [
                        "vina",
                        "--receptor",
                        receptor_pdbqt.name,
                        "--ligand",
                        lig_pdbqt.name,
                        "--config",
                        conf_path.name,
                        "--out",
                        out_name,
                        "--cpu",
                        str(self.config.cpu_per_job),
                        "--exhaustiveness",
                        str(self.config.exhaustiveness),
                    ],
                    work_dir=complex_dir,
                )
                out_path = complex_dir / out_name
                score = self._extract_best_score(out_path) if rc == 0 else None
                return rc, out_path, score

            max_workers = max(1, settings.get_threads() // max(1, self.config.cpu_per_job))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                job_results = list(executor.map(_run_single_vina, range(1, self.config.times + 1)))

            scored = sorted(
                [(path, score) for rc, path, score in job_results if rc == 0 and score is not None],
                key=lambda item: item[1],
            )
            if not scored:
                self.log(f"[{complex_name}] No successful docking results.", logging.WARNING)
                continue

            best_file, best_score = scored[0]
            shutil.copy2(best_file, self.bests_dir / best_file.name)
            final_results.append(
                {
                    "complex": complex_name,
                    "best_pose": str(self.bests_dir / best_file.name),
                    "best_score_kcal_mol": best_score,
                }
            )
            self.log(f"{lig_pdbqt.stem}: {best_score:.3f} kcal/mol")

        self.log(f"Docking complete. {len(final_results)} complex(es) done.")
        return {
            "status": "completed",
            "results": final_results,
            "output_dir": str(self.output_dir),
        }


def run_docking_pipeline(**kwargs: Any) -> dict[str, Any]:
    """Run the docking pipeline with explicit keyword arguments."""
    output_dir = kwargs.pop("output_dir", None)
    on_output = kwargs.pop("on_output", None)
    max_mode = kwargs.pop("max_resources", False)
    protein_pdb = kwargs.pop("protein_pdb")
    ligands_sdf = kwargs.pop("ligands_sdf")
    pipeline = DockingPipeline(
        output_dir=output_dir,
        on_output=on_output,
        max_mode=max_mode,
        **kwargs,
    )
    return pipeline.run(protein_pdb=protein_pdb, ligands_sdf=ligands_sdf)
