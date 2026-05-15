"""Boltz-1 structure prediction pipeline."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

from bimos.config.settings import settings
from bimos.infrastructure import container
from bimos.prediction.confidence import pick_best_boltz
from bimos.prediction.fasta import write_boltz_yaml
from bimos.shared.pipeline import Pipeline
from bimos.shared.user_config import resolve

logger = logging.getLogger("bimos.prediction.boltz")


class BoltzPipeline(Pipeline):
    """Protein structure prediction via Boltz-1."""

    workspace_subdir = "boltz"

    def _build_cli_args(self, yaml_name: str, model_dir: str, cfg: dict[str, Any]) -> list[str]:
        args = [
            "boltz",
            "predict",
            f"/workspace/{yaml_name}",
            "--out_dir",
            model_dir,
            "--recycling_steps",
            str(cfg["recycling_steps"]),
            "--sampling_steps",
            str(cfg["sampling_steps"]),
            "--diffusion_samples",
            str(cfg["diffusion_samples"]),
            "--max_parallel_samples",
            str(cfg["max_parallel_samples"]),
            "--step_scale",
            str(cfg["step_scale"]),
            "--max_msa_seqs",
            str(cfg["max_msa_seqs"]),
            "--num_subsampled_msa",
            str(cfg["num_subsampled_msa"]),
            "--num_workers",
            str(cfg["num_workers"]),
            "--preprocessing-threads",
            str(cfg["preprocessing_threads"]),
            "--output_format",
            cfg["output_format"],
        ]
        if cfg.get("use_msa_server"):
            args += ["--use_msa_server", "--msa_pairing_strategy", cfg["msa_pairing_strategy"]]
        if cfg.get("subsample_msa"):
            args.append("--subsample_msa")
        if cfg.get("use_potentials"):
            args.append("--use_potentials")
        if cfg.get("write_full_pae"):
            args.append("--write_full_pae")
        if cfg.get("write_full_pde"):
            args.append("--write_full_pde")
        if cfg.get("override"):
            args.append("--override")
        if cfg.get("no_kernels"):
            args.append("--no_kernels")
        return args

    def run(
        self,
        fasta_path: str,
        num_models: int = 5,
        max_mode: bool | None = None,
    ) -> dict[str, Any]:
        fasta = Path(fasta_path).resolve()
        job_dir = self.output_dir / fasta.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = job_dir / f"{fasta.stem}.yaml"
        write_boltz_yaml(fasta, yaml_path)

        pred_dir = job_dir / "predictions"
        pred_dir.mkdir(exist_ok=True)
        cfg, profile = resolve("boltz", max_mode=max_mode)
        self.log(f"Boltz profile: {profile.value}")

        cache_dir = settings.cache_path / "boltz"
        cache_dir.mkdir(parents=True, exist_ok=True)
        volumes = {str(job_dir): "/workspace", str(cache_dir): "/workspace/.boltz_cache"}
        env = {"BOLTZ_CACHE_DIR": "/workspace/.boltz_cache"}

        self.log(f"Starting Boltz prediction ({num_models} models)")
        for index in range(1, num_models + 1):
            model_out = pred_dir / f"model_{index}"
            model_out.mkdir(exist_ok=True)
            self.log(f"Running model {index}/{num_models}...")
            cmd = self._build_cli_args(yaml_path.name, f"/workspace/predictions/model_{index}", cfg)
            container.run(
                command=cmd,
                image=settings.bimos_image,
                volumes=volumes,
                workdir="/workspace",
                env=env,
                on_output=self.on_output,
            )

        best = pick_best_boltz(pred_dir)
        if not best:
            raise RuntimeError("No valid Boltz output.")

        dest_struct = job_dir / f"{fasta.stem}_best{best['struct_path'].suffix}"
        dest_json = job_dir / f"{fasta.stem}_best_conf.json"
        shutil.copy2(best["struct_path"], dest_struct)
        shutil.copy2(best["json_path"], dest_json)
        self.log(f"Best model selected. Score: {best['score']:.4f}")
        return {
            "status": "completed",
            "struct_file": str(dest_struct),
            "confidence": round(best["score"], 4),
            "output_dir": str(job_dir),
        }


def predict_boltz(**kwargs: Any) -> dict[str, Any]:
    output_dir = kwargs.pop("output_dir", None)
    on_output = kwargs.pop("on_output", None)
    max_mode = kwargs.pop("max_resources", False)
    return BoltzPipeline(output_dir=output_dir, on_output=on_output).run(
        max_mode=max_mode,
        **kwargs,
    )
