"""ESMFold structure prediction pipeline."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any, Callable

from bimos.config.settings import settings
from bimos.infrastructure import container
from bimos.prediction.confidence import pick_best_esmfold
from bimos.prediction.fasta import write_boltz_yaml
from bimos.shared.paths import SCRIPTS_DIR
from bimos.shared.pipeline import Pipeline
from bimos.shared.user_config import resolve

logger = logging.getLogger("bimos.prediction.esmfold")


class ESMFoldPipeline(Pipeline):
    """Protein structure prediction via ESMFold."""

    workspace_subdir = "predict"

    def _ensure_model(self) -> Path:
        cache_dir = settings.esm_cache_path
        cache_dir.mkdir(parents=True, exist_ok=True)
        model = cache_dir / "esmfold.model"
        if model.exists():
            return cache_dir

        model_url = getattr(settings, "esm_model_url", None)
        if not model_url:
            raise RuntimeError(
                "ESMFold model URL not configured. "
                "Set BIMOS_ESM_MODEL_URL or ESM_MODEL_URL in .env"
            )

        self.log(f"Downloading ESMFold model (~8 GB) to {model} ...")
        if shutil.which("aria2c"):
            cmd = [
                "aria2c",
                "-x",
                "16",
                "-s",
                "16",
                "-d",
                str(cache_dir),
                "-o",
                "esmfold.model",
                model_url,
            ]
        elif shutil.which("wget"):
            cmd = ["wget", "-O", str(model), model_url]
        else:
            cmd = ["curl", "-L", "-o", str(model), model_url]

        if container.run(command=cmd, on_output=self.on_output) != 0 or not model.exists():
            raise RuntimeError("Failed to download ESMFold model.")
        return cache_dir

    def run(  # type: ignore[override]
        self,
        fasta_path: str,
        num_recycles: int | None = None,
        max_mode: bool | None = None,
    ) -> dict[str, Any]:
        cfg, profile = resolve("esmfold", max_mode=max_mode)
        if num_recycles is None:
            num_recycles = int(cfg.get("prediction", {}).get("num_recycles", 3))
        self.log(f"ESMFold profile: {profile.value}")

        fasta = Path(fasta_path).resolve()
        job_dir = self.output_dir / fasta.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = job_dir / f"{fasta.stem}.yaml"
        write_boltz_yaml(fasta, yaml_path)
        cache_dir = self._ensure_model()

        pred_dir = job_dir / "predictions"
        pred_dir.mkdir(exist_ok=True)
        volumes = {
            str(job_dir): "/workspace",
            str(cache_dir): "/models",
            str(SCRIPTS_DIR): "/app",
        }
        cmd = [
            "python3",
            "/app/predict_esm.py",
            f"/workspace/{yaml_path.name}",
            "--out_dir",
            "/workspace/predictions",
            "--num_recycles",
            str(num_recycles),
        ]

        self.log(f"Starting ESMFold prediction for {fasta.name}")
        rc = container.run(
            command=cmd,
            image=settings.bimos_image,
            volumes=volumes,
            workdir="/workspace",
            on_output=self.on_output,
        )
        if rc != 0:
            raise RuntimeError(f"ESMFold exited with code {rc}")

        best = pick_best_esmfold(pred_dir)
        if not best:
            raise RuntimeError("No valid ESMFold output.")

        dest_pdb = job_dir / f"{fasta.stem}_best.pdb"
        shutil.copy(best["pdb_path"], dest_pdb)
        self.log(f"Prediction complete. Confidence: {best['score']:.4f}")
        return {
            "status": "completed",
            "pdb_file": str(dest_pdb),
            "confidence": round(best["score"], 4),
            "output_dir": str(job_dir),
        }


def predict_structure(**kwargs: Any) -> dict[str, Any]:
    output_dir = kwargs.pop("output_dir", None)
    on_output = kwargs.pop("on_output", None)
    max_mode = kwargs.pop("max_resources", False)
    return ESMFoldPipeline(output_dir=output_dir, on_output=on_output).run(
        max_mode=max_mode,
        **kwargs,
    )
