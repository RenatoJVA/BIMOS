"""
Job management endpoints.
"""

from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from bimos.infrastructure.job_store import store
from bimos.api.schemas import JobResponse
from bimos.api.utils import job_to_response, get_job_or_404

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=list[JobResponse])
async def list_jobs():
    """List all jobs in the current session."""
    return [job_to_response(j) for j in store.list_all()]

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):
    """Get the status of a specific job."""
    return job_to_response(get_job_or_404(job_id))

@router.get("/{job_id}/logs")
async def get_job_logs(job_id: str, tail: Optional[int] = Query(None)):
    """Return captured log lines for a job."""
    get_job_or_404(job_id)
    return {"job_id": job_id, "logs": store.get_logs(job_id, tail=tail)}

@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):
    """Cancel a running job."""
    if not store.cancel(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"status": "canceled", "job_id": job_id}

@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str):
    """Remove a job from the store."""
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
