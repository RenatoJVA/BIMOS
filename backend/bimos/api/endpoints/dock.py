"""
Molecular docking endpoints.
"""

from typing import Any, Optional

from fastapi import APIRouter, File, Form, UploadFile

from bimos.api.schemas import JobResponse
from bimos.api.utils import dispatch_job, job_to_response, safe_filename
from bimos.config.settings import settings
from bimos.docking import run_docking_pipeline
from bimos.infrastructure.job_store import store

router = APIRouter(tags=["Docking"])


@router.post("/dock", response_model=JobResponse, status_code=202)
async def dock_job(  # type: ignore[no-untyped-def]
    protein: UploadFile = File(...),
    ligands: UploadFile = File(...),
    max_resources: bool = Form(False),
    times: Optional[int] = Form(None),
    exhaustiveness: Optional[int] = Form(None),
    num_modes: Optional[int] = Form(None),
    margin: Optional[float] = Form(None),
    cpu_per_job: Optional[int] = Form(None),
):
    """Submit a docking job. Parameters omitted use ``~/.bimos/config/docking.yaml``."""
    safe_protein = safe_filename(protein.filename)
    safe_ligands = safe_filename(ligands.filename)
    job_dir = settings.workspace_path / "docking" / safe_protein.replace(".pdb", "")
    job_dir.mkdir(parents=True, exist_ok=True)

    pdb_path = job_dir / safe_protein
    sdf_path = job_dir / safe_ligands
    pdb_path.write_bytes(await protein.read())
    sdf_path.write_bytes(await ligands.read())

    overrides: dict[str, Any] = {}
    for key, value in {
        "times": times,
        "exhaustiveness": exhaustiveness,
        "num_modes": num_modes,
        "margin": margin,
        "cpu_per_job": cpu_per_job,
    }.items():
        if value is not None:
            overrides[key] = value

    job = store.create(
        kind="dock",
        meta={"protein": str(pdb_path), "ligands": str(sdf_path), "max_resources": max_resources},
        output_dir=str(job_dir),
    )
    dispatch_job(
        run_docking_pipeline,
        job.id,
        output_dir=str(job_dir),
        protein_pdb=str(pdb_path),
        ligands_sdf=str(sdf_path),
        max_resources=max_resources,
        **overrides,
    )
    return job_to_response(job)
