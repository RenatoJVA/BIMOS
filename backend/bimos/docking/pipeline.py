"""
Molecular docking pipeline using AutoDock Vina.
"""

from __future__ import annotations

import logging
import math
import shutil
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from bimos.config.settings import settings
from bimos.docking.config import DockingConfig, _check_size
from bimos.docking.pocket import (
    LARGE_BOX_WARN,
    box_from_extent,
    center_from_residues,
    parse_pocket_residues,
    read_sdf_first_molecule_coords,
)
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
        center: tuple[float, float, float] | list[float] | None = None,
        size: tuple[float, float, float] | list[float] | None = None,
        center_on: str | Path | None = None,
        pocket_residues: str | None = None,
        padding: float | None = None,
        **vina_overrides: Any,
    ) -> None:
        super().__init__(output_dir, on_output)
        self.config = DockingConfig.resolve(max_mode=max_mode, **vina_overrides)
        # Fail fast: validate the requested search box before any container work.
        self.req_center = _check_triplet(center, "center")
        self.req_size = _check_triplet(size, "size")
        if self.req_size is not None:
            names = ("size_x", "size_y", "size_z")
            self.req_size = tuple(_check_size(v, n) for v, n in zip(self.req_size, names, strict=True))
        self.req_center_on = Path(center_on) if center_on else None
        if self.req_center_on is not None and not self.req_center_on.exists():
            raise FileNotFoundError(f"Reference ligand not found: {self.req_center_on}")
        self.req_pocket = parse_pocket_residues(pocket_residues) if pocket_residues else None
        self.req_padding = float(padding) if padding is not None else None
        if self.req_padding is not None and self.req_padding < 0:
            raise ValueError(f"Invalid padding {padding}: must be >= 0.")
        _check_grid_combo(
            center=self.req_center,
            size=self.req_size,
            center_on=self.req_center_on,
            pocket=self.req_pocket,
            padding=self.req_padding,
        )

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
            read_only={"/scripts"},
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

    def _resolve_grid(self, pdbqt_path: Path) -> tuple[str, tuple[float, ...], tuple[float, ...]]:
        """Effective ``(mode, center, size)``: explicit > center-on > pocket > yaml > auto."""
        padding = self.req_padding if self.req_padding is not None else self.config.margin
        if self.req_center is not None or self.req_size is not None:
            if self.req_center is None or self.req_size is None:
                raise ValueError("--center and --size must be provided together.")
            return "manual", self.req_center, self.req_size
        if self.req_center_on is not None:
            coords, _ = read_sdf_first_molecule_coords(self.req_center_on)
            xs = [c[0] for c in coords]
            ys = [c[1] for c in coords]
            zs = [c[2] for c in coords]
            center = (sum(xs) / len(xs), sum(ys) / len(ys), sum(zs) / len(zs))
            span = (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))
            self.log(f"Center from reference {self.req_center_on.name} ({len(coords)} atoms)")
            return "center-on", center, box_from_extent(span, padding)
        if self.req_pocket is not None:
            center, n, span = center_from_residues(pdbqt_path, self.req_pocket)
            self.log(f"Center from {len(self.req_pocket)} residues ({n} atoms)")
            return "pocket", center, box_from_extent(span, padding)
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
            return (
                "manual",
                tuple(required[:3]),  # type: ignore[arg-type]
                tuple(required[3:]),  # type: ignore[arg-type]
            )
        xs, ys, zs = self._read_coords(pdbqt_path)
        if not xs:
            raise ValueError(f"No ATOM/HETATM coordinates found in {pdbqt_path}")
        center = tuple(sum(values) / len(values) for values in (xs, ys, zs))
        size = tuple(max(values) - min(values) + self.config.margin for values in (xs, ys, zs))
        return "auto", center, size

    def _write_grid_box_conf(self, pdbqt_path: Path, conf_path: Path) -> None:
        mode, center, size = self._resolve_grid(pdbqt_path)
        cx, cy, cz = (round(v, 3) for v in center)
        sx, sy, sz = (round(v, 3) for v in size)
        if any(v > LARGE_BOX_WARN for v in (sx, sy, sz)):
            self.log(
                f"Grid {mode}: large box ({sx}x{sy}x{sz} A) — "
                "covers much of the receptor (nearly blind)",
                logging.WARNING,
            )
        if mode != "auto":
            xs, ys, zs = self._read_coords(pdbqt_path)
            if xs and (
                cx - sx / 2 <= min(xs) and cx + sx / 2 >= max(xs)
                and cy - sy / 2 <= min(ys) and cy + sy / 2 >= max(ys)
                and cz - sz / 2 <= min(zs) and cz + sz / 2 >= max(zs)
            ):
                self.log("Targeted grid covers the WHOLE receptor (de facto blind)", logging.WARNING)
        self.log(f"Grid {mode}: center=({cx}, {cy}, {cz}) size=({sx}, {sy}, {sz})")
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
            [
                "python3",
                "/scripts/prepare_receptor.py",
                "--input",
                pdb_path.name,
                "--output",
                pdbqt_path.name,
            ],
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

    def run(self, protein_pdb: str, ligands_sdf: str) -> dict[str, Any]:  # type: ignore[override]
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

            def _run_single_vina(
                run_index: int,
                *,
                complex_name: str = complex_name,
                receptor_pdbqt: Path = receptor_pdbqt,
                lig_pdbqt: Path = lig_pdbqt,
                conf_path: Path = conf_path,
                complex_dir: Path = complex_dir,
            ) -> tuple[int, Path, float | None]:
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


_TRIPLET_LEN = 3


def _check_triplet(value: tuple[float, float, float] | list[float] | None, name: str) -> tuple[float, float, float] | None:
    if value is None:
        return None
    try:
        items = tuple(float(v) for v in value)
    except (TypeError, ValueError):
        raise ValueError(f"--{name} requires 3 numbers (e.g. --{name} 12.5 3.1 -0.4).") from None
    if len(items) != _TRIPLET_LEN:
        raise ValueError(f"--{name} requires exactly {_TRIPLET_LEN} numbers (got {len(items)}).")
    if any(math.isnan(v) or math.isinf(v) for v in items):
        raise ValueError(f"--{name} contains non-finite values.")
    return items  # type: ignore[return-value]


def _check_grid_combo(
    center: tuple[float, float, float] | None,
    size: tuple[float, float, float] | None,
    center_on: Path | None,
    pocket: list[tuple[str | None, int]] | None,
    padding: float | None,
) -> None:
    if (center is None) != (size is None):
        raise ValueError("--center and --size must be provided together.")
    derived = [s for s in (center_on is not None, pocket is not None) if s]
    if center is not None and derived:
        raise ValueError("--center/--size is incompatible with --center-on/--pocket-residues (pick one).")
    if center_on is not None and pocket is not None:
        raise ValueError("--center-on and --pocket-residues are mutually exclusive (pick one).")
    if padding is not None and center_on is None and pocket is None:
        raise ValueError("--padding only applies with --center-on or --pocket-residues.")


def run_docking_pipeline(**kwargs: Any) -> dict[str, Any]:
    """Run the docking pipeline with explicit keyword arguments."""
    output_dir = kwargs.pop("output_dir", None)
    on_output = kwargs.pop("on_output", None)
    max_mode = kwargs.pop("max_resources", None)
    protein_pdb = kwargs.pop("protein_pdb")
    ligands_sdf = kwargs.pop("ligands_sdf")
    pipeline = DockingPipeline(
        output_dir=output_dir,
        on_output=on_output,
        max_mode=max_mode,
        **kwargs,
    )
    return pipeline.run(protein_pdb=protein_pdb, ligands_sdf=ligands_sdf)
