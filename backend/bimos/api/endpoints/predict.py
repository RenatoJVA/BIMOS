"""
Structure prediction endpoints.
"""

from fastapi import APIRouter

from bimos.api.schemas import JobResponse, PredictBoltzRequest, PredictRequest
from bimos.api.utils import dispatch_job, job_to_response
from bimos.config.settings import settings
from bimos.infrastructure.job_store import store
from bimos.prediction import predict_boltz, predict_structure

router = APIRouter(tags=["Prediction"])


@router.post("/predict", response_model=JobResponse, status_code=202)
async def predict_esm(req: PredictRequest):
    """Submit an ESMFold prediction job."""
    job_dir = settings.workspace_path / "predict" / req.name
    job_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = job_dir / f"{req.name}.fasta"
    fasta_path.write_text(req.fasta_content)

    job = store.create(
        kind="predict",
        meta={"name": req.name, "fasta": str(fasta_path), "max_resources": req.max_resources},
        output_dir=str(job_dir),
    )
    kwargs: dict = {
        "output_dir": str(job_dir),
        "fasta_path": str(fasta_path),
        "max_resources": req.max_resources,
    }
    if req.num_recycles is not None:
        kwargs["num_recycles"] = req.num_recycles

    dispatch_job(predict_structure, job.id, **kwargs)
    return job_to_response(store.get(job.id))


@router.post("/predict-boltz", response_model=JobResponse, status_code=202)
async def predict_boltz_job(req: PredictBoltzRequest):
    """Submit a Boltz-1 prediction job."""
    job_dir = settings.workspace_path / "boltz" / req.name
    job_dir.mkdir(parents=True, exist_ok=True)
    fasta_path = job_dir / f"{req.name}.fasta"
    fasta_path.write_text(req.fasta_content)

    job = store.create(
        kind="predict-boltz",
        meta={"name": req.name, "fasta": str(fasta_path), "max_resources": req.max_resources},
        output_dir=str(job_dir),
    )
    kwargs: dict = {
        "output_dir": str(job_dir),
        "fasta_path": str(fasta_path),
        "max_resources": req.max_resources,
    }
    if req.num_models is not None:
        kwargs["num_models"] = req.num_models

    dispatch_job(predict_boltz, job.id, **kwargs)
    return job_to_response(store.get(job.id))
