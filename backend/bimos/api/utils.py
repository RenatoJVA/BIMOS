"""
API utilities for job dispatching and response formatting.
"""

import os
import re
import threading
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile

from bimos.api.schemas import JobResponse
from bimos.infrastructure import cancellation
from bimos.infrastructure.job_store import JobRecord, JobStatus, current_job_id, store

SAFE_NAME_RE = re.compile(r"^[a-zA-Z0-9_.-]+$")
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def safe_filename(filename: str | None) -> str:
    if not filename:
        raise HTTPException(status_code=422, detail="Filename is required")
    basename = os.path.basename(filename)
    if not basename or basename.startswith(".") or "/" in basename:
        raise HTTPException(status_code=422, detail=f"Invalid filename: {filename}")
    if not SAFE_NAME_RE.match(basename):
        raise HTTPException(status_code=422, detail=f"Invalid filename: {filename}")
    return basename


def new_job_dir(category: str, name: str) -> Path:
    """Create a unique output directory so concurrent jobs never overwrite files."""
    from bimos.config.settings import settings

    safe = safe_filename(name)
    stem = Path(safe).stem or "job"
    base = settings.workspace_path / category
    base.mkdir(parents=True, exist_ok=True)
    for _ in range(10):
        candidate = base / f"{stem}-{uuid.uuid4().hex[:10]}"
        try:
            candidate.mkdir()
            return candidate
        except FileExistsError:
            continue
    raise HTTPException(status_code=500, detail="Could not allocate a unique job directory.")


async def read_upload(upload: UploadFile, max_bytes: int | None = None) -> bytes:
    """Read an upload with a hard size cap instead of trusting Content-Length."""
    limit = MAX_UPLOAD_BYTES if max_bytes is None else max_bytes
    chunks: list[bytes] = []
    total = 0
    while chunk := await upload.read(1024 * 1024):
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"Upload '{upload.filename}' exceeds the {limit // (1024 * 1024)} MB limit.",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def job_to_response(j: JobRecord) -> JobResponse:
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
        results=j.results,
    )


def get_job_or_404(job_id: str) -> JobRecord:
    job = store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return job


def dispatch_job(fn: Callable[..., Any], job_id: str, **kwargs: Any) -> None:
    """Run *fn* in a background daemon thread; update job store on completion."""
    max_resources = kwargs.pop("max_resources", False)

    def _worker() -> None:
        current_job_id.set(job_id)
        cancel_event = cancellation.register(job_id)
        cancellation.current_cancel_event.set(cancel_event)
        job = store.get(job_id)
        if cancellation.is_canceled(job_id) or (
            job is not None and job.status == JobStatus.CANCELED
        ):
            cancellation.unregister(job_id)
            return
        store.start(job_id)
        try:
            result = fn(
                on_output=lambda line: store.log(job_id, line),
                max_resources=max_resources,
                **kwargs,
            )
            if cancellation.is_canceled(job_id):
                return
            store.complete(job_id, exit_code=0, results=result)
        except Exception as exc:
            if cancellation.is_canceled(job_id):
                return
            store.fail(job_id, str(exc))
        finally:
            cancellation.unregister(job_id)

    threading.Thread(target=_worker, daemon=True).start()
