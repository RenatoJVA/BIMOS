"""
Quantum mechanics pipelines for ORCA and Gaussian Hirshfeld charge extraction.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any, Callable

from bimos.config.settings import settings
from bimos.quantum_chemistry.config import GaussianConfig, OrcaConfig
from bimos.quantum_chemistry.elements import atomic_number
from bimos.quantum_chemistry.itp import update_itp_charges
from bimos.shared.pipeline import Pipeline
from bimos.shared.templates import render_template

logger = logging.getLogger("bimos.quantum_chemistry")

ORCA_TEMPLATE = Path(__file__).parent / "templates" / "orca.inp.template"
GAUSSIAN_TEMPLATE = Path(__file__).parent / "templates" / "gaussian.gjf.template"


class QMPipeline(Pipeline):
    """Shared QM utilities for multiplicity and file conversion."""

    workspace_subdir = "qm"

    def __init__(
        self,
        output_dir: str | Path | None = None,
        on_output: Callable[[str], None] | None = None,
        charge: int = 0,
        max_jobs: int = 2,
        max_mode: bool | None = None,
    ) -> None:
        super().__init__(output_dir, on_output)
        self.charge = charge
        self.max_jobs = max_jobs
        self.max_mode = max_mode

    def _calc_multiplicity(self, xyz_lines: list[str]) -> int:
        total_electrons = 0
        for line in xyz_lines:
            parts = line.split()
            if not parts:
                continue
            total_electrons += atomic_number(parts[0])
        total_electrons -= self.charge
        return 1 if total_electrons % 2 == 0 else 2

    @staticmethod
    def _gro_to_xyz(gro: Path, directory: Path) -> tuple[Path, list[str]]:
        xyz_path = directory / f"{gro.stem}.xyz"
        subprocess.run(
            ["obabel", str(gro), "-oxyz", "-O", str(xyz_path)],
            check=True,
            capture_output=True,
        )
        xyz_content = xyz_path.read_text(encoding="utf-8").splitlines()
        return xyz_path, xyz_content[2:]


class OrcaPipeline(QMPipeline):
    """ORCA Hirshfeld charge pipeline."""

    def run(self, directory: str) -> dict[str, Any]:  # type: ignore[override]
        dir_path = Path(directory).resolve()
        orca_bin = settings.orca_path
        if not orca_bin or not Path(orca_bin).exists():
            raise FileNotFoundError("ORCA binary not found. Configure ORCA_PATH in .env")

        cfg = OrcaConfig.resolve(max_mode=self.max_mode, charge=self.charge)
        self.log(f"ORCA profile: {cfg.profile}")
        gro_files = sorted(dir_path.glob("*.gro"))
        self.log(f"Found {len(gro_files)} .gro files in {dir_path}")

        processes: list[tuple[subprocess.Popen[bytes], Any, Path]] = []
        for gro in gro_files:
            inp_path = gro.with_suffix(".inp")
            _, atoms = self._gro_to_xyz(gro, dir_path)
            mult = self._calc_multiplicity(atoms)
            coordinates = "\n".join(atoms)

            inp_path.write_text(
                render_template(
                    ORCA_TEMPLATE,
                    method=cfg.method,
                    basis=cfg.basis,
                    nprocs=cfg.nprocs,
                    maxcore=cfg.maxcore_mb,
                    max_iter=cfg.max_iter,
                    charge=self.charge,
                    multiplicity=mult,
                    coordinates=coordinates,
                ),
                encoding="utf-8",
            )

            out_path = inp_path.with_suffix(".out")
            env = dict(os.environ)
            orca_dir = str(Path(orca_bin).parent)
            env["PATH"] = f"{orca_dir}:{env.get('PATH', '')}"
            env["LD_LIBRARY_PATH"] = f"{orca_dir}:{env.get('LD_LIBRARY_PATH', '')}"
            env["OMP_NUM_THREADS"] = str(cfg.nprocs)

            while len([item for item in processes if item[0].poll() is None]) >= cfg.max_jobs:
                time.sleep(1)

            self.log(f"Launching ORCA for {gro.name}")
            with open(out_path, "w", encoding="utf-8") as out_file:
                proc = subprocess.Popen(
                    [orca_bin, inp_path.name],
                    stdout=out_file,
                    stderr=out_file,
                    cwd=str(dir_path),
                    env=env,
                )
            processes.append((proc, gro))

        for proc, gro in processes:
            try:
                proc.wait(timeout=86400)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.log(f"ORCA process timed out for {gro.name}", level="WARNING")

        results: list[str] = []
        pattern = re.compile(r"^\s*\d+\s+[A-Z][a-zA-Z]?\s+([-]?\d+\.\d+)")
        for gro in gro_files:
            itp = gro.with_suffix(".itp")
            out = gro.with_suffix(".out")
            if not itp.exists() or "ORCA TERMINATED NORMALLY" not in out.read_text(errors="replace"):
                self.log(f"Skipping {gro.name}: ITP missing or ORCA failed", logging.WARNING)
                continue

            charges: list[float] = []
            inside = False
            with open(out, encoding="utf-8") as handle:
                for line in handle:
                    if "HIRSHFELD ANALYSIS" in line:
                        inside = True
                        continue
                    if inside and ("TOTAL" in line or "Sum" in line):
                        break
                    if inside:
                        match = pattern.match(line)
                        if match:
                            charges.append(float(match.group(1)))

            if charges:
                self.log(f"Updating {itp.name} with {len(charges)} charges")
                results.append(str(update_itp_charges(itp, charges)))

        return {"status": "completed", "results": results}


class GaussianPipeline(QMPipeline):
    """Gaussian Hirshfeld charge pipeline."""

    def run(self, directory: str) -> dict[str, Any]:  # type: ignore[override]
        dir_path = Path(directory).resolve()
        g16_bin = settings.gaussian_path
        if not g16_bin or not Path(g16_bin).exists():
            raise FileNotFoundError("Gaussian binary not found. Configure GAUSSIAN_PATH in .env")

        cfg = GaussianConfig.resolve(max_mode=self.max_mode, charge=self.charge)
        self.log(f"Gaussian profile: {cfg.profile}")
        gro_files = sorted(dir_path.glob("*.gro"))
        self.log(f"Found {len(gro_files)} .gro files in {dir_path}")

        processes: list[tuple[subprocess.Popen[bytes], Any, Path]] = []
        for gro in gro_files:
            gjf_path = gro.with_suffix(".gjf")
            _, atoms = self._gro_to_xyz(gro, dir_path)
            mult = self._calc_multiplicity(atoms)
            coordinates = "\n".join(line.strip() for line in atoms)

            gjf_path.write_text(
                render_template(
                    GAUSSIAN_TEMPLATE,
                    chk_name=f"{gjf_path.stem}.chk",
                    mem=cfg.mem,
                    nprocs=cfg.nprocs,
                    route=cfg.route,
                    title=f"{gro.stem} QM calculation",
                    charge=self.charge,
                    multiplicity=mult,
                    coordinates=coordinates,
                ),
                encoding="utf-8",
            )

            log_path = gjf_path.with_suffix(".log")

            while len([item for item in processes if item[0].poll() is None]) >= cfg.max_jobs:
                time.sleep(1)

            self.log(f"Launching Gaussian for {gro.name}")
            with open(log_path, "w", encoding="utf-8") as log_file:
                proc = subprocess.Popen(
                    [g16_bin, gjf_path.name],
                    stdout=log_file,
                    stderr=log_file,
                    cwd=str(dir_path),
                )
            processes.append((proc, gro))

        for proc, gro in processes:
            try:
                proc.wait(timeout=86400)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                self.log(f"Gaussian process timed out for {gro.name}", level="WARNING")

        results: list[str] = []
        pattern = re.compile(r"^\s*(\d+)\s+([A-Z][a-zA-Z]?)\s+([-]?\d+\.\d+)")
        for gro in gro_files:
            itp = gro.with_suffix(".itp")
            log_path = gro.with_suffix(".log")
            if not itp.exists() or "Normal termination of Gaussian" not in log_path.read_text(errors="replace"):
                self.log(f"Skipping {gro.name}: ITP missing or Gaussian failed", logging.WARNING)
                continue

            charges: list[float] = []
            inside = False
            with open(log_path, encoding="utf-8") as handle:
                for line in handle:
                    if "Hirshfeld charges, spin densities" in line:
                        inside = True
                        continue
                    if not inside:
                        continue
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] == "Tot":
                        break
                    match = pattern.match(line)
                    if match:
                        charges.append(float(match.group(3)))

            if charges:
                self.log(f"Updating {itp.name} with {len(charges)} charges")
                results.append(str(update_itp_charges(itp, charges)))

        return {"status": "completed", "results": results}


def run_orca_pipeline(directory: str, **kwargs: Any) -> dict[str, Any]:
    max_mode = kwargs.pop("max_resources", False)
    return OrcaPipeline(max_mode=max_mode, **kwargs).run(directory)


def run_gaussian_pipeline(directory: str, **kwargs: Any) -> dict[str, Any]:
    max_mode = kwargs.pop("max_resources", False)
    return GaussianPipeline(max_mode=max_mode, **kwargs).run(directory)
