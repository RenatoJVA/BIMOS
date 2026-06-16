"""
Job management endpoints.
"""

import json
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from bimos.infrastructure.job_store import store
from bimos.api.schemas import JobResponse
from bimos.api.utils import job_to_response, get_job_or_404

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
async def get_job_logs(job_id: str, tail: Optional[int] = Query(None)):  # type: ignore[no-untyped-def]
    """Return captured log lines for a job."""
    get_job_or_404(job_id)
    return {"job_id": job_id, "logs": store.get_logs(job_id, tail=tail)}

@router.post("/{job_id}/cancel")
async def cancel_job(job_id: str):  # type: ignore[no-untyped-def]
    """Cancel a running job."""
    if not store.cancel(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"status": "canceled", "job_id": job_id}

@router.delete("/{job_id}", status_code=204)
async def delete_job(job_id: str):  # type: ignore[no-untyped-def]
    """Remove a job from the store."""
    if not store.delete(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")

@router.get("/{job_id}/logs/stream")
async def stream_job_logs(job_id: str):  # type: ignore[no-untyped-def]
    """SSE endpoint that streams new log lines as they are written."""
    import asyncio

    get_job_or_404(job_id)
    last_len = 0

    async def _event_stream():
        nonlocal last_len
        while True:
            logs = store.get_logs(job_id)
            new_lines = logs[last_len:]
            for line in new_lines:
                yield f"data: {json.dumps({'line': line})}\n\n"
            last_len = len(logs)
            try:
                await asyncio.sleep(1)
            except asyncio.CancelledError:
                break

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
