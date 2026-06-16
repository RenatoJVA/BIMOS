"""
Simulation (MD/QM) endpoints.
"""

from fastapi import APIRouter, File, Form, UploadFile

from bimos.api.schemas import JobResponse
from bimos.api.utils import dispatch_job, job_to_response, safe_filename
from bimos.config.settings import settings
from bimos.infrastructure.job_store import store
from bimos.molecular_dynamics import run_md_simulation
from bimos.quantum_chemistry import run_orca_pipeline

router = APIRouter(tags=["Simulation"])


@router.post("/simulate", response_model=JobResponse, status_code=202)
async def simulate_apo(  # type: ignore[no-untyped-def]
    protein: UploadFile = File(...),
    max_resources: bool = Form(False),
):
    """Submit a GROMACS MD simulation job (Apo)."""
    safe_protein = safe_filename(protein.filename)
    job_dir = settings.workspace_path / "md" / f"Apo-{safe_protein.replace('.pdb', '')}"
    job_dir.mkdir(parents=True, exist_ok=True)
    pdb_path = job_dir / safe_protein
    pdb_path.write_bytes(await protein.read())

    job = store.create(
        kind="simulate",
        meta={"pdb": str(pdb_path), "max_resources": max_resources},
        output_dir=str(job_dir),
    )
    dispatch_job(
        run_md_simulation,
        job.id,
        output_dir=str(job_dir),
        pdb_path=str(pdb_path),
        max_resources=max_resources,
    )
    return job_to_response(job)


@router.post("/simulate-holo", response_model=JobResponse, status_code=202)
async def simulate_holo(  # type: ignore[no-untyped-def]
    protein: UploadFile = File(...),
    ligand_gro: UploadFile = File(...),
    ligand_itp: UploadFile = File(...),
    max_resources: bool = Form(False),
):
    """Submit a GROMACS MD simulation job (Holo)."""
    safe_protein = safe_filename(protein.filename)
    safe_gro = safe_filename(ligand_gro.filename)
    safe_itp = safe_filename(ligand_itp.filename)
    job_dir = settings.workspace_path / "md" / f"Holo-{safe_protein.replace('.pdb', '')}"
    job_dir.mkdir(parents=True, exist_ok=True)

    pdb_path = job_dir / safe_protein
    gro_path = job_dir / safe_gro
    itp_path = job_dir / safe_itp

    pdb_path.write_bytes(await protein.read())
    gro_path.write_bytes(await ligand_gro.read())
    itp_path.write_bytes(await ligand_itp.read())

    job = store.create(
        kind="simulate-holo",
        meta={
            "pdb": str(pdb_path),
            "ligand_gro": str(gro_path),
            "ligand_itp": str(itp_path),
            "max_resources": max_resources,
        },
        output_dir=str(job_dir),
    )
    dispatch_job(
        run_md_simulation,
        job.id,
        output_dir=str(job_dir),
        pdb_path=str(pdb_path),
        ligand_gro=str(gro_path),
        ligand_itp=str(itp_path),
        max_resources=max_resources,
    )
    return job_to_response(job)


@router.post("/qm-orca-files", response_model=JobResponse, status_code=202)
async def qm_orca(  # type: ignore[no-untyped-def]
    gro: UploadFile = File(...),
    itp: UploadFile = File(...),
    charge: int = Form(0),
    max_resources: bool = Form(False),
):
    """Submit an ORCA QM calculation job."""
    safe_gro = safe_filename(gro.filename)
    safe_itp = safe_filename(itp.filename)
    job_dir = settings.workspace_path / "qm" / safe_gro.replace(".gro", "")
    job_dir.mkdir(parents=True, exist_ok=True)

    gro_path = job_dir / safe_gro
    itp_path = job_dir / safe_itp
    gro_path.write_bytes(await gro.read())
    itp_path.write_bytes(await itp.read())

    job = store.create(
        kind="qm-orca",
        meta={
            "gro": str(gro_path),
            "itp": str(itp_path),
            "charge": charge,
            "max_resources": max_resources,
        },
        output_dir=str(job_dir),
    )
    dispatch_job(
        run_orca_pipeline,
        job.id,
        directory=str(job_dir),
        charge=charge,
        max_resources=max_resources,
    )
    return job_to_response(job)
