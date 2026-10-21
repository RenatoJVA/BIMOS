"""Boltz-2 structure prediction pipeline."""

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from bimos.config.settings import settings
from bimos.infrastructure import container
from bimos.prediction.confidence import pick_best_boltz
from bimos.prediction.fasta import ensure_yaml
from bimos.shared.pipeline import Pipeline
from bimos.shared.user_config import resolve

logger = logging.getLogger("bimos.prediction.boltz")


REQUIRED_KEYS = {"recycling_steps", "sampling_steps", "diffusion_samples",
                 "max_parallel_samples", "num_models", "output_format",
                 "step_scale", "max_msa_seqs", "num_subsampled_msa",
                 "num_workers", "preprocessing_threads"}

# ``model`` is optional so configs written before the Boltz-2 migration keep
# working; Boltz-2 is the default and the only model BIMOS ships weights for.
DEFAULT_MODEL = "boltz2"
SUPPORTED_MODELS = ("boltz1", "boltz2")

# Tuned defaults per model, used when the user config predates the migration
# and still carries Boltz-1 values.
LEGACY_STEP_SCALE = 1.638
TUNED_STEP_SCALE = {"boltz1": 1.638, "boltz2": 1.5}


def _apply_model_override(
    cfg: dict[str, Any], model: str, log: Any = None
) -> dict[str, Any]:
    """Return *cfg* switched to *model*, with that model's tuned step_scale.

    ``step_scale`` is tuned per model (1.638 for Boltz-1, 1.5 for Boltz-2).
    Selecting a model from the command line therefore has to move it too, or
    ``--model boltz1`` would quietly run the Boltz-1 weights with the Boltz-2
    sampling scale. The packaged config already pairs them correctly, so this
    only changes anything when the two actually disagree.
    """
    if model not in SUPPORTED_MODELS:
        raise ValueError(f"model must be one of {SUPPORTED_MODELS}, got {model!r}")
    tuned = TUNED_STEP_SCALE[model]
    current = float(cfg.get("step_scale", tuned))
    if log is not None and current != tuned:
        log(
            "--model %s selected; using its tuned step_scale %s instead of %s",
            model,
            tuned,
            current,
        )
    return {**cfg, "model": model, "step_scale": tuned}


class _GpuHostMonitor:
    """Sample host ``nvidia-smi`` while a Boltz model runs.

    Boltz spends most wall time on CPU (checkpoint load, MSA fetch,
    preprocessing) and only brief bursts on the GPU during diffusion
    sampling, which makes an instantaneous ``nvidia-smi`` reading look
    idle even though inference runs on CUDA. Sampling utilization
    throughout the run and reporting avg/max captures those bursts, so
    the log keeps hard evidence that the GPU is actually being used
    instead of a silent CPU fallback.
    """

    def __init__(self, log: Any) -> None:
        self._log = log
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.samples: list[tuple[float, float]] = []

    def start(self) -> None:
        if shutil.which("nvidia-smi") is None:
            self._log("[GPU evidence] (host) nvidia-smi not found; skipping monitor")
            return
        self._thread = threading.Thread(target=self._poll, daemon=True)
        self._thread.start()

    def _poll(self) -> None:
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used",
            "--format=csv,noheader,nounits",
        ]
        while not self._stop.is_set():
            try:
                out = subprocess.run(  # noqa: S603 - fixed argv, no shell
                    cmd, capture_output=True, text=True, timeout=5
                )
                if out.returncode == 0 and out.stdout.strip():
                    first = out.stdout.strip().splitlines()[0]
                    util, mem = (p.strip() for p in first.split(","))
                    self.samples.append((float(util), float(mem)))
            except Exception:  # noqa: S110 - monitoring must never break predict
                pass
            time.sleep(2)

    def stop_and_report(self) -> None:
        if self._thread is None:
            return
        self._stop.set()
        self._thread.join(timeout=10)
        if not self.samples:
            self._log("[GPU evidence] (host) no nvidia-smi samples collected")
            return
        utils = [u for u, _ in self.samples]
        mems = [m for _, m in self.samples]
        avg_util = sum(utils) / len(utils)
        report = (
            f"[GPU evidence] (host) samples={len(self.samples)} "
            f"util% avg={avg_util:.1f} max={max(utils):.0f} | "
            f"mem avg={sum(mems) // len(mems)} MiB peak={max(mems)} MiB"
        )
        self._log(report)


class BoltzPipeline(Pipeline):
    """Protein structure prediction via Boltz-2."""

    workspace_subdir = "boltz"

    @staticmethod
    def _validate_config(cfg: dict[str, Any]) -> None:
        missing = REQUIRED_KEYS - set(cfg.keys())
        if missing:
            raise ValueError(f"Boltz config missing required keys: {missing}")
        if cfg.get("num_models", 0) < 1:
            raise ValueError("num_models must be >= 1")
        model = cfg.get("model", DEFAULT_MODEL)
        if model not in SUPPORTED_MODELS:
            raise ValueError(
                f"model must be one of {SUPPORTED_MODELS}, got {model!r}"
            )

    @staticmethod
    def _warn_legacy_config(cfg: dict[str, Any]) -> None:
        """Flag configs written before the Boltz-2 migration.

        Packaged defaults are copied to ``~/.bimos/config`` on first run and
        never refreshed, so an untouched file from a Boltz-1 install keeps the
        old ``step_scale`` (1.638) instead of the Boltz-2 tuned 1.5. We do not
        silently rewrite user files, so say it out loud instead.
        """
        if "model" in cfg:
            return
        from bimos.shared.user_config import _user_path

        tuned = TUNED_STEP_SCALE[cfg.get("model", DEFAULT_MODEL)]
        if float(cfg.get("step_scale", tuned)) == tuned:
            return
        logger.warning(
            "%s predates the Boltz-2 migration: it has no 'model' key and keeps "
            "the Boltz-1 step_scale %s (Boltz-2 is tuned for %s). Delete that file "
            "to regenerate it with the Boltz-2 defaults.",
            _user_path("boltz"),
            cfg.get("step_scale"),
            tuned,
        )

    def _build_cli_args(self, yaml_name: str, model_dir: str, cfg: dict[str, Any]) -> list[str]:
        self._validate_config(cfg)
        args = [
            "boltz",
            "predict",
            f"/workspace/{yaml_name}",
            "--out_dir",
            model_dir,
            "--cache",
            "/workspace/.boltz_cache",
            # Pinned explicitly: Boltz-2 changed this default to boltz2 in
            # 2.x, and we never want the engine to change silently.
            "--model",
            cfg.get("model", DEFAULT_MODEL),
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

    def _run_in_container(self, cmd: list[str]) -> int:
        """Run a short command inside the BIMOS image for diagnostics."""
        return container.run(
            command=cmd,
            image=settings.bimos_image,
            volumes={str(self.output_dir): "/workspace"},
            workdir="/workspace",
            on_output=self.on_output,
        )

    def _preflight_gpu(self) -> None:
        """Verify the GPU is usable inside the container before starting.

        Two levels: the NVIDIA driver (``nvidia-smi``) and the actual CUDA
        context PyTorch resolves inside the container. Boltz on CPU is
        impractically slow, so we fail fast with a clear diagnostic instead
        of letting the job crawl or silently downgrade.
        """
        cmd = ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"]
        if self._run_in_container(cmd) != 0:
            raise RuntimeError(
                "GPU not available inside the container for Boltz. "
                "Ensure NVIDIA drivers + CDI are configured and pass the GPU "
                "device (e.g. `--device nvidia.com/gpu=all` with podman)."
            )
        torch_check = [
            "python3",
            "-c",
            "import torch; assert torch.cuda.is_available(), 'torch sees no CUDA device'; "
            "n = torch.cuda.get_device_name(0); print(f'torch CUDA ready: {n}')",
        ]
        if self._run_in_container(torch_check) != 0:
            raise RuntimeError(
                "nvidia-smi works but PyTorch cannot see the CUDA device inside "
                "the container (CPU-only wheel or driver/runtime mismatch). "
                "BIMOS forbids silent CPU fallback for Boltz; rebuild or repair "
                "the CUDA image before predicting."
            )

    def _gpu_evidence(self, model_index: int) -> None:
        """Post-run proof: the GPU context stayed observable after the model."""
        cmd = [
            "nvidia-smi",
            "--query-gpu=utilization.gpu,memory.used",
            "--format=csv,noheader",
        ]
        if self._run_in_container(cmd) != 0:
            raise RuntimeError(
                f"GPU became unavailable during Boltz model {model_index}. "
                "Check driver stability / CDI device passthrough."
            )

    def run(  # type: ignore[override]
        self,
        fasta_path: str,
        num_models: int = 5,
        max_mode: bool | None = None,
        model: str | None = None,
    ) -> dict[str, Any]:
        input_path = Path(fasta_path).resolve()
        job_dir = self.output_dir / input_path.stem
        job_dir.mkdir(parents=True, exist_ok=True)

        yaml_path = ensure_yaml(input_path, job_dir)

        pred_dir = job_dir / "predictions"
        pred_dir.mkdir(exist_ok=True)
        cfg, profile = resolve("boltz", max_mode=max_mode)
        if model is not None:
            cfg = _apply_model_override(cfg, model, logger.info)
        self.log(f"Boltz profile: {profile.value}")
        self._warn_legacy_config(cfg)

        cache_dir = settings.cache_path / "boltz"
        cache_dir.mkdir(parents=True, exist_ok=True)
        volumes = {str(job_dir): "/workspace", str(cache_dir): "/workspace/.boltz_cache"}
        env = {"BOLTZ_CACHE": "/workspace/.boltz_cache", "BOLTZ_CACHE_DIR": "/workspace/.boltz_cache"}

        self._preflight_gpu()

        self.log(f"Starting Boltz prediction ({num_models} models)")
        for index in range(1, num_models + 1):
            model_out = pred_dir / f"model_{index}"
            model_out.mkdir(exist_ok=True)
            self.log(f"Running model {index}/{num_models}...")
            cmd = self._build_cli_args(yaml_path.name, f"/workspace/predictions/model_{index}", cfg)
            monitor = _GpuHostMonitor(self.log)
            monitor.start()
            try:
                rc = container.run(
                    command=cmd,
                    image=settings.bimos_image,
                    volumes=volumes,
                    workdir="/workspace",
                    env=env,
                    on_output=self.on_output,
                )
            finally:
                monitor.stop_and_report()
            if rc != 0:
                raise RuntimeError(
                    f"Boltz prediction failed for model {index}/{num_models} (exit {rc})."
                )
            self._gpu_evidence(index)

        best = pick_best_boltz(pred_dir)
        if not best:
            raise RuntimeError("No valid Boltz output.")

        dest_struct = job_dir / f"{input_path.stem}_best{best['struct_path'].suffix}"
        dest_json = job_dir / f"{input_path.stem}_best_conf.json"
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
