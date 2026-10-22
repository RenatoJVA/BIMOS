"""
Job management endpoints.
"""

import json

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from bimos.api.schemas import JobResponse
from bimos.api.utils import get_job_or_404, job_to_response
from bimos.infrastructure.job_store import JobStatus, store

router = APIRouter(prefix="/jobs", tags=["Jobs"])

@router.get("", response_model=list[JobResponse])
async def list_jobs():  # type: ignore[no-untyped-def]
    """List all jobs in the current session."""
    return [job_to_response(j) for j in store.list_all()]

@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str):  # type: ignore[no-untyped-def]
    """Get the status of a specific job."""
    return job_to_response(get_job_or_404(job_id))

@router.get("/{job_id}/logs")
async def get_job_logs(job_id: str, tail: int | None = Query(None)):  # type: ignore[no-untyped-def]
    """Return captured log lines for a job."""
    get_job_or_404(job_id)
    return {"job_id": job_id, "logs": store.get_logs(job_id, tail=tail)}

@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):  # type: ignore[no-untyped-def]
    """Cancel a pending/running job. Terminal jobs are never overwritten."""
    get_job_or_404(job_id)
    if not store.cancel(job_id):
        raise HTTPException(
            status_code=409,
            detail=f"Job '{job_id}' is already finished and cannot be canceled.",
        )
    return {"status": "canceled", "job_id": job_id}

@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str):  # type: ignore[no-untyped-def]
    """Remove a job from the store."""
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

@router.get("/{job_id}/logs/stream")
async def stream_job_logs(
    job_id: str,
    offset: int | None = Query(None, ge=0),
):  # type: ignore[no-untyped-def]
    """SSE endpoint that streams log lines from *offset* and closes on finish."""
    import asyncio

    get_job_or_404(job_id)
    position = offset or 0

    async def _event_stream():
        nonlocal position
        while True:
            chunk, position = store.read_log_chunk(job_id, position)
            for line in chunk.splitlines():
                if line:
                    yield f"data: {json.dumps({'line': line})}\n\n"

            job = store.get(job_id)
            if job is None or job.status in {
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELED,
            }:
                status = job.status.value if job is not None else "deleted"
                yield f"data: {json.dumps({'status': status})}\n\n"
                break

            try:
                await asyncio.sleep(0.5)
            except asyncio.CancelledError:
                return

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
