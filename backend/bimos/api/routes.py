"""
BIMOS FastAPI routes.

Exposes the same core functions as the CLI but over HTTP.
All long-running jobs are dispatched in background threads and tracked
via the in-memory job store. Clients can poll /jobs/{job_id} for status.
"""

import threading
from typing import Optional, Any

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel

from bimos.infrastructure.job_store import store, JobRecord

router = APIRouter(prefix="/api/v1")


# ── Schemas ───────────────────────────────────────────────────────────────────

class JobResponse(BaseModel):
    id: str
    kind: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    output_dir: Optional[str] = None
    meta: dict[str, Any] = {}


class PredictRequest(BaseModel):
    fasta_content: str
    name: str = "protein"
    num_recycles: int = 3


class PredictBoltzRequest(BaseModel):
    fasta_content: str
    name: str = "protein"
    num_models: int = 5


class DockRequest(BaseModel):
    times: int = 1
    exhaustiveness: int = 8
    num_modes: int = 9
    margin: float = 1.0
    cpu_per_job: int = 4


class SimulateRequest(BaseModel):
    pass  # Uses defaults; MDP customization can be added later


class QMRequest(BaseModel):
    orca_input: str  # Full content of the .inp file


# ── Job helpers ───────────────────────────────────────────────────────────────

def _job_to_response(j: JobRecord) -> JobResponse:
    return JobResponse(
        id=j.id,
        kind=j.kind,
        status=j.status,
        created_at=j.created_at,
        started_at=j.started_at,
        finished_at=j.finished_at,
        error=j.error,
        output_dir=j.output_dir,
        meta=j.meta,
    )


def _get_job_or_404(job_id: str) -> JobRecord:
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


def _dispatch(fn, job_id: str, **kwargs) -> None:
    """Run fn in a background daemon thread; update job store on completion."""
    def _worker():
        store.start(job_id)
        try:
            fn(on_output=lambda line: store.log(job_id, line), **kwargs)
            store.complete(job_id, exit_code=0)
        except Exception as exc:
            store.fail(job_id, str(exc))

    threading.Thread(target=_worker, daemon=True).start()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {"status": "ok"}


# ── Prediction ────────────────────────────────────────────────────────────────

@router.post("/predict", response_model=JobResponse, status_code=202)
async def predict_structure(req: PredictRequest):
    """Submit a protein structure prediction job (ESMFold)."""
    from bimos.config.settings import settings

    job_dir = settings.workspace_path / "predict" / req.name
    job_dir.mkdir(parents=True, exist_ok=True)

    fasta_path = job_dir / f"{req.name}.fasta"
    fasta_path.write_text(req.fasta_content)

    job = store.create(
        kind="predict",
        meta={"name": req.name, "fasta": str(fasta_path)},
        output_dir=str(job_dir),
    )

    from bimos.core.protein import predict_structure as _predict
    _dispatch(
        _predict,
        job.id,
        fasta_path=str(fasta_path),
        output_dir=str(job_dir),
        num_recycles=req.num_recycles,
    )

    return _job_to_response(store.get(job.id))


@router.post("/predict-boltz", response_model=JobResponse, status_code=202)
async def predict_boltz(req: PredictBoltzRequest):
    """Submit a protein structure prediction job (Boltz-1)."""
    from bimos.config.settings import settings

    job_dir = settings.workspace_path / "boltz" / req.name
    job_dir.mkdir(parents=True, exist_ok=True)

    fasta_path = job_dir / f"{req.name}.fasta"
    fasta_path.write_text(req.fasta_content)

    job = store.create(
        kind="predict-boltz",
        meta={"name": req.name, "fasta": str(fasta_path)},
        output_dir=str(job_dir),
    )

    from bimos.core.boltz import predict_boltz as _boltz
    _dispatch(
        _boltz,
        job.id,
        fasta_path=str(fasta_path),
        output_dir=str(job_dir),
        num_models=req.num_models,
    )

    return _job_to_response(store.get(job.id))


# ── Docking ───────────────────────────────────────────────────────────────────

@router.post("/dock", response_model=JobResponse, status_code=202)
async def dock(
    protein: UploadFile = File(...),
    ligands: UploadFile = File(...),
    times: int = Form(1),
    exhaustiveness: int = Form(8),
    num_modes: int = Form(9),
    margin: float = Form(1.0),
    cpu_per_job: int = Form(4),
):
    """Submit a docking job (PDB + SDF files)."""
    from bimos.config.settings import settings

    job_dir = settings.workspace_path / "docking" / protein.filename.replace(".pdb", "")
    job_dir.mkdir(parents=True, exist_ok=True)

    pdb_path = job_dir / protein.filename
    sdf_path = job_dir / ligands.filename
    pdb_path.write_bytes(await protein.read())
    sdf_path.write_bytes(await ligands.read())

    job = store.create(
        kind="dock",
        meta={"protein": str(pdb_path), "ligands": str(sdf_path)},
        output_dir=str(job_dir),
    )

    from bimos.core.docking import run_docking_pipeline
    _dispatch(
        run_docking_pipeline,
        job.id,
        protein_pdb=str(pdb_path),
        ligands_sdf=str(sdf_path),
        output_dir=str(job_dir),
        times=times,
        exhaustiveness=exhaustiveness,
        num_modes=num_modes,
        margin=margin,
        cpu_per_job=cpu_per_job,
    )

    return _job_to_response(store.get(job.id))


# ── Simulation ────────────────────────────────────────────────────────────────

@router.post("/simulate", response_model=JobResponse, status_code=202)
async def simulate(protein: UploadFile = File(...)):
    """Submit a GROMACS MD simulation job (Apo)."""
    from bimos.config.settings import settings
    job_dir = settings.workspace_path / "md" / f"Apo-{protein.filename.replace('.pdb', '')}"
    job_dir.mkdir(parents=True, exist_ok=True)
    pdb_path = job_dir / protein.filename
    pdb_path.write_bytes(await protein.read())

    job = store.create(kind="simulate", meta={"pdb": str(pdb_path)}, output_dir=str(job_dir))
    from bimos.core.workflow import run_md_simulation
    _dispatch(run_md_simulation, job.id, pdb_path=str(pdb_path), output_dir=str(job_dir))
    return _job_to_response(store.get(job.id))


@router.post("/simulate-holo", response_model=JobResponse, status_code=202)
async def simulate_holo(
    protein: UploadFile = File(...),
    ligand_gro: UploadFile = File(...),
    ligand_itp: UploadFile = File(...),
):
    """Submit a GROMACS MD simulation job (Holo)."""
    from bimos.config.settings import settings
    job_dir = settings.workspace_path / "md" / f"Holo-{protein.filename.replace('.pdb', '')}"
    job_dir.mkdir(parents=True, exist_ok=True)
    
    pdb_path = job_dir / protein.filename
    gro_path = job_dir / ligand_gro.filename
    itp_path = job_dir / ligand_itp.filename
    
    pdb_path.write_bytes(await protein.read())
    gro_path.write_bytes(await ligand_gro.read())
    itp_path.write_bytes(await ligand_itp.read())

    job = store.create(
        kind="simulate-holo",
        meta={"pdb": str(pdb_path), "ligand_gro": str(gro_path), "ligand_itp": str(itp_path)},
        output_dir=str(job_dir)
    )
    from bimos.core.workflow import run_md_simulation
    _dispatch(
        run_md_simulation,
        job.id,
        pdb_path=str(pdb_path),
        ligand_gro=str(gro_path),
        ligand_itp=str(itp_path),
        output_dir=str(job_dir)
    )
    return _job_to_response(store.get(job.id))


# ── QM ────────────────────────────────────────────────────────────────────────

@router.post("/qm", response_model=JobResponse, status_code=202)
async def run_qm(req: QMRequest):
    """Submit an ORCA QM calculation job."""
    from bimos.config.settings import settings

    job_dir = settings.workspace_path / "qm"
    job_dir.mkdir(parents=True, exist_ok=True)
    inp_path = job_dir / "input.inp"
    inp_path.write_text(req.orca_input)

    job = store.create(
        kind="qm",
        meta={"input": str(inp_path)},
        output_dir=str(job_dir),
    )

    from bimos.core.workflow import run_qm_calculation
    _dispatch(run_qm_calculation, job.id, input_file=str(inp_path), output_dir=str(job_dir))

    return _job_to_response(store.get(job.id))


# ── Job tracking ──────────────────────────────────────────────────────────────

@router.get("/jobs", response_model=list[JobResponse])
async def list_jobs():
    """List all jobs in the current session."""
    return [_job_to_response(j) for j in store.list_all()]


@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get the status of a specific job."""
    return _job_to_response(_get_job_or_404(job_id))


@router.get("/jobs/{job_id}/logs")
async def get_job_logs(job_id: str):
    """Return all captured log lines for a job."""
    _get_job_or_404(job_id)
    return {"job_id": job_id, "logs": store.get_logs(job_id)}


@router.delete("/jobs/{job_id}", status_code=204)
async def delete_job(job_id: str):
    """Remove a job from the store."""
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")


# ── Ligand database ───────────────────────────────────────────────────────────

@router.get("/ligands")
async def list_ligands(
    q: str = Query("", description="Search term (name, CID, or SMILES substring)."),
    source: Optional[str] = Query(None, description="Filter by source."),
    limit: int = Query(50, le=500),
):
    """Search the ligand database."""
    from bimos.infrastructure.database import search_ligands

    try:
        results = search_ligands(query=q, source=source, limit=limit)
        return {
            "count": len(results),
            "ligands": [
                {
                    "id": r.id,
                    "name": r.name,
                    "cid": r.cid,
                    "smiles": r.smiles,
                    "logp": r.logp,
                    "molar_mass": r.molar_mass,
                    "source": r.source,
                }
                for r in results
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
