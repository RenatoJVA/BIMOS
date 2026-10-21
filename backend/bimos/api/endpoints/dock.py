"""
Molecular docking endpoints.
"""

from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

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
    times: int | None = Form(None),
    exhaustiveness: int | None = Form(None),
    num_modes: int | None = Form(None),
    margin: float | None = Form(None),
    cpu_per_job: int | None = Form(None),
    center_x: float | None = Form(None),
    center_y: float | None = Form(None),
    center_z: float | None = Form(None),
    size_x: float | None = Form(None),
    size_y: float | None = Form(None),
    size_z: float | None = Form(None),
    pocket_residues: str | None = Form(None),
    padding: float | None = Form(None),
    reference: UploadFile | None = File(None),
):
    """Submit a docking job. Parameters omitted use ``~/.bimos/config/docking.yaml``."""
    center = (center_x, center_y, center_z)
    size = (size_x, size_y, size_z)
    if any(v is None for v in (*center, *size)) and any(v is not None for v in (*center, *size)):
        raise HTTPException(status_code=400, detail="center_x/y/z and size_x/y/z must be complete (all 6).")
    if any(v is not None for v in size) and all(v is None for v in center) and reference is None and not pocket_residues:
        raise HTTPException(status_code=400, detail="size without center/reference/pocket_residues defines no location.")
    if all(v is None for v in center) and reference is not None and pocket_residues:
        raise HTTPException(status_code=400, detail="reference and pocket_residues are mutually exclusive.")

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
    if all(v is not None for v in center):
        overrides["center"] = (center_x, center_y, center_z)
    if all(v is not None for v in size):
        overrides["size"] = (size_x, size_y, size_z)
    if pocket_residues:
        overrides["pocket_residues"] = pocket_residues
    if padding is not None:
        overrides["padding"] = padding
    if reference is not None and reference.filename:
        # Kept in the job dir as evidence of the site used.
        ref_path = job_dir / f"reference_{safe_filename(reference.filename)}"
        ref_path.write_bytes(await reference.read())
        overrides["center_on"] = str(ref_path)

    job = store.create(
        kind="dock",
        meta={
            "protein": str(pdb_path),
            "ligands": str(sdf_path),
            "max_resources": max_resources,
            "grid": {k: v for k, v in overrides.items() if k in {"center", "size", "center_on", "pocket_residues", "padding"}},
        },
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
