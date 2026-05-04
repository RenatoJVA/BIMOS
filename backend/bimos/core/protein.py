"""
Protein structure prediction via ESMFold.

Workflow:
  1. Parse input FASTA and extract sequences.
  2. Build a YAML file that the predict_esm.py script expects.
  3. Ensure the ESMFold model weight is cached (~8 GB, downloaded once).
  4. Run the container: image → predict_esm.py → PDB + confidence JSON.
  5. Pick the best model by confidence score and copy it to output_dir.
"""

import json
import glob
import shutil
import logging
from pathlib import Path
from typing import Callable, Optional

from bimos.config.settings import settings
from bimos.infrastructure import container

logger = logging.getLogger("bimos.protein")

# Path to predict_esm.py relative to this file (bimos/core/ → bimos/scripts/)
_SCRIPT_DIR = Path(__file__).parent.parent / "scripts"


def _build_yaml(fasta_path: Path, yaml_path: Path) -> str:
    """
    Parse a FASTA file and produce a Boltz-style YAML for predict_esm.py.
    Returns the joined sequence string for reference.
    """
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

    # Build YAML
    yaml_lines = ["sequences:"]
    for seq in sequences:
        yaml_lines.append("  - protein:")
        yaml_lines.append(f"      sequence: {seq}")

    yaml_path.write_text("\n".join(yaml_lines) + "\n")
    logger.debug("YAML written to %s (%d sequences)", yaml_path, len(sequences))
    return ":".join(sequences)


def _ensure_model(on_output: Optional[Callable[[str], None]] = None) -> Path:
    """
    Ensure the ESMFold model weight exists.  Downloads it if absent.
    Returns the cache directory path.
    """
    cache_dir = settings.esm_cache_path
    cache_dir.mkdir(parents=True, exist_ok=True)
    model_file = cache_dir / "esmfold.model"

    if model_file.exists():
        return cache_dir

    msg = f"ESMFold model not found. Downloading (~8 GB) to {model_file} ..."
    logger.info(msg)
    if on_output:
        on_output(f"[BIMOS] {msg}")

    # Prefer aria2c for speed, fall back to wget
    if shutil.which("aria2c"):
        cmd = [
            "aria2c", "-x", "16", "-s", "16",
            "-d", str(cache_dir), "-o", "esmfold.model",
            settings.esm_model_url,
        ]
    elif shutil.which("wget"):
        cmd = ["wget", "-O", str(model_file), settings.esm_model_url]
    else:
        cmd = ["curl", "-L", "-o", str(model_file), settings.esm_model_url]

    rc = container.run(command=cmd, on_output=on_output)
    if rc != 0 or not model_file.exists():
        raise RuntimeError("Failed to download ESMFold model.")

    return cache_dir


def _pick_best(pred_dir: Path) -> Optional[dict]:
    """Return the PDB with the highest confidence score in pred_dir."""
    best: Optional[dict] = None
    for json_path in glob.glob(str(pred_dir / "**" / "confidence_*.json"), recursive=True):
        try:
            with open(json_path) as f:
                data = json.load(f)
        except Exception:
            continue

        score = data.get("confidence_score") or data.get("plddt", 0)
        pdb_stem = Path(json_path).stem.replace("confidence_", "")
        pdb_path = Path(json_path).parent / f"{pdb_stem}.pdb"

        if pdb_path.exists() and (best is None or score > best["score"]):
            best = {"score": score, "pdb_path": str(pdb_path), "data": data}

    return best


def predict_structure(
    fasta_path: str,
    output_dir: Optional[str] = None,
    num_recycles: int = 3,
    on_output: Optional[Callable[[str], None]] = None,
) -> dict:
    """
    Predict protein structure from a FASTA file using ESMFold.

    Args:
        fasta_path: Path to the input FASTA file.
        output_dir: Directory where results are saved.
        num_recycles: ESMFold recycling iterations (3 = good balance).
        on_output: Line-by-line output callback.

    Returns:
        dict with keys: status, pdb_file, confidence, output_dir
    """
    fasta_path = Path(fasta_path).resolve()
    if not fasta_path.exists():
        raise FileNotFoundError(f"FASTA not found: {fasta_path}")

    if output_dir:
        job_dir = Path(output_dir)
    else:
        job_dir = settings.workspace_path / "predict" / fasta_path.stem
    job_dir.mkdir(parents=True, exist_ok=True)

    # Generate YAML inside the job directory
    yaml_path = job_dir / f"{fasta_path.stem}.yaml"
    _build_yaml(fasta_path, yaml_path)

    # Ensure model weights
    cache_dir = _ensure_model(on_output=on_output)

    # Directories visible inside the container
    pred_subdir = job_dir / "predictions"
    pred_subdir.mkdir(exist_ok=True)

    container_workspace = "/workspace"

    volumes = {
        str(job_dir): container_workspace,
        str(cache_dir): "/models",
        str(_SCRIPT_DIR): "/app",
    }

    cmd = [
        "python3", "/app/predict_esm.py",
        f"{container_workspace}/{yaml_path.name}",
        "--out_dir", f"{container_workspace}/predictions",
        "--num_recycles", str(num_recycles),
    ]

    if on_output:
        on_output(f"[BIMOS] Starting ESMFold prediction for {fasta_path.name}")

    rc = container.run(
        command=cmd,
        image=settings.bimos_image,
        volumes=volumes,
        workdir=container_workspace,
        on_output=on_output,
    )

    if rc != 0:
        raise RuntimeError(f"ESMFold container exited with code {rc}")

    best = _pick_best(pred_subdir)
    if not best:
        raise RuntimeError("No valid PDB output from ESMFold.")

    # Copy best model to job root
    dest_pdb = job_dir / f"{fasta_path.stem}_best.pdb"
    shutil.copy(best["pdb_path"], dest_pdb)

    result = {
        "status": "completed",
        "pdb_file": str(dest_pdb),
        "confidence": round(best["score"], 4),
        "output_dir": str(job_dir),
    }

    if on_output:
        on_output(f"[BIMOS] Prediction complete. Confidence: {result['confidence']:.4f}")
        on_output(f"[BIMOS] PDB saved to: {dest_pdb}")

    return result
