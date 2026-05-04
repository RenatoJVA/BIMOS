"""
Protein structure prediction via Boltz-1.
Ported from robust user scripts with multi-model sampling and best-model selection.
"""

import json
import glob
import shutil
import logging
from pathlib import Path
from typing import Callable, Optional

from bimos.config.settings import settings
from bimos.infrastructure import container

logger = logging.getLogger("bimos.boltz")

def _build_yaml(fasta_path: Path, yaml_path: Path) -> None:
    """Build a Boltz-style YAML from a FASTA file."""
    sequences: list[str] = []
    current_seq: list[str] = []

    with open(fasta_path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            if line.startswith(">"):
                if current_seq:
                    sequences.append("".join(current_seq))
                current_seq = []
            else:
                current_seq.append(line)

    if current_seq:
        sequences.append("".join(current_seq))

    if not sequences:
        raise ValueError(f"No sequences found in {fasta_path}")

    # Build Boltz YAML format
    yaml_lines = ["sequences:"]
    for seq in sequences:
        yaml_lines.append("  - protein:")
        yaml_lines.append(f"      sequence: {seq}")

    yaml_path.write_text("\n".join(yaml_lines) + "\n")


def _pick_best(pred_root: Path) -> Optional[dict]:
    """Find the best model by confidence score in a prediction root."""
    best: Optional[dict] = None
    # Boltz outputs confidence in JSON files
    for json_path in glob.glob(str(pred_root / "**" / "confidence_*.json"), recursive=True):
        try:
            with open(json_path) as f:
                data = json.load(f)
        except Exception:
            continue

        score = data.get("confidence_score")
        if score is None:
            continue
            
        # Try to find corresponding structure file (.cif or .pdb)
        stem = Path(json_path).name.replace("confidence_", "").replace(".json", "")
        parent = Path(json_path).parent
        struct_path = None
        for ext in [".cif", ".pdb"]:
            p = parent / (stem + ext)
            if p.exists():
                struct_path = p
                break
        
        if struct_path and (best is None or score > best["score"]):
            best = {
                "score": score,
                "data": data,
                "struct_path": struct_path,
                "json_path": Path(json_path),
            }
    return best


def predict_boltz(
    fasta_path: str,
    output_dir: Optional[str] = None,
    num_models: int = 5,
    on_output: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Full Boltz prediction pipeline: YAML generation -> N models -> Best selection.
    """
    fasta_path = Path(fasta_path).resolve()
    if not fasta_path.exists():
        raise FileNotFoundError(f"FASTA not found: {fasta_path}")

    job_dir = Path(output_dir) if output_dir else settings.workspace_path / "boltz" / fasta_path.stem
    job_dir.mkdir(parents=True, exist_ok=True)

    # 1. Prepare YAML
    yaml_path = job_dir / f"{fasta_path.stem}.yaml"
    _build_yaml(fasta_path, yaml_path)

    # 2. Run N models
    pred_dir = job_dir / "predictions"
    pred_dir.mkdir(exist_ok=True)

    if on_output:
        on_output(f"[BIMOS] Starting Boltz prediction ({num_models} models)")

    for i in range(1, num_models + 1):
        model_out = pred_dir / f"model_{i}"
        model_out.mkdir(exist_ok=True)
        
        if on_output:
            on_output(f"[BIMOS] Running model {i}/{num_models}...")

        # Construct command matching old/Boltz.py exactly
        cmd = [
            "boltz", "predict", f"/workspace/{yaml_path.name}",
            "--out_dir", f"/workspace/predictions/model_{i}",
            "--recycling_steps", "10",
            "--sampling_steps", "200",
            "--diffusion_samples", "50",
            "--max_parallel_samples", "6",
            "--step_scale", "1.638",
            "--use_msa_server",
            "--msa_pairing_strategy", "complete",
            "--max_msa_seqs", "8192",
            "--num_subsampled_msa", "1024",
            "--subsample_msa",
            "--use_potentials",
            "--output_format", "mmcif",
            "--write_full_pae",
            "--write_full_pde",
            "--num_workers", "8",
            "--preprocessing-threads", "16",
            "--override",
            "--no_kernels",
        ]

        # Boltz cache dir from host to avoid re-downloading weights/MSAs
        cache_dir = settings.cache_path / "boltz"
        cache_dir.mkdir(parents=True, exist_ok=True)

        env = {"BOLTZ_CACHE_DIR": "/workspace/.boltz_cache"}
        volumes = {
            str(job_dir): "/workspace",
            str(cache_dir): "/workspace/.boltz_cache",
        }

        rc = container.run(
            command=cmd,
            image=settings.bimos_image,
            volumes=volumes,
            workdir="/workspace",
            env=env,
            on_output=on_output,
        )

        if rc != 0:
            logger.warning(f"Boltz model {i} failed with code {rc}")

    # 3. Select Best
    best = _pick_best(pred_dir)
    if not best:
        raise RuntimeError("No valid output from Boltz models.")

    # Copy best results to job root
    dest_struct = job_dir / f"{fasta_path.stem}_best{best['struct_path'].suffix}"
    dest_json = job_dir / f"{fasta_path.stem}_best_conf.json"
    shutil.copy2(best["struct_path"], dest_struct)
    shutil.copy2(best["json_path"], dest_json)

    result = {
        "status": "completed",
        "struct_file": str(dest_struct),
        "confidence": round(best["score"], 4),
        "output_dir": str(job_dir),
    }

    if on_output:
        on_output(f"[BIMOS] Best model selected. Score: {result['confidence']:.4f}")
        on_output(f"[BIMOS] Output saved to: {dest_struct}")

    return result
