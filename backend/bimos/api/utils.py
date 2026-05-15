"""
API utilities for job dispatching and response formatting.
"""

import threading
from typing import Any, Callable

from fastapi import HTTPException

from bimos.api.schemas import JobResponse
from bimos.infrastructure.job_store import store, JobRecord, current_job_id


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


def dispatch_job(fn: Callable, job_id: str, **kwargs: Any) -> None:
    """Run *fn* in a background daemon thread; update job store on completion."""
    max_resources = kwargs.pop("max_resources", False)

    def _worker() -> None:
        current_job_id.set(job_id)
        store.start(job_id)
        try:
            result = fn(
                on_output=lambda line: store.log(job_id, line),
                max_resources=max_resources,
                **kwargs,
            )
            store.complete(job_id, exit_code=0, results=result)
        except Exception as exc:
            store.fail(job_id, str(exc))

    threading.Thread(target=_worker, daemon=True).start()
