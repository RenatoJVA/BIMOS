"""
Persistent, thread-safe Job Store for BIMOS.
Stores jobs as JSON files and logs as plain text in the workspace.
This allows multiple CLI processes and the GUI server to share the same state.
"""

import threading
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel
from contextvars import ContextVar

from bimos.config.settings import settings

current_job_id: ContextVar[str] = ContextVar("current_job_id", default="")


class JobStatus(StrEnum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"
    CANCELED  = "canceled"


class JobRecord(BaseModel):
    id: str
    kind: str
    status: JobStatus
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    output_dir: Optional[str] = None
    meta: dict[str, Any] = {}
    results: Optional[Any] = None


class FileJobStore:
    def __init__(self) -> None:
        self.jobs_dir = settings.workspace_path / ".jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _log_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.log"

    def _save(self, job: JobRecord) -> None:
        with self._lock:
            self._path(job.id).write_text(job.model_dump_json(indent=2))

    def _load(self, job_id: str) -> Optional[JobRecord]:
        p = self._path(job_id)
        if not p.exists():
            return None
        try:
            return JobRecord.model_validate_json(p.read_text())
        except Exception:
            return None

    def create(self, kind: str, meta: dict[str, Any] = None, output_dir: str = "") -> JobRecord:
        import uuid
        job_id = uuid.uuid4().hex[:12]
        job = JobRecord(
            id=job_id,
            kind=kind,
            status=JobStatus.PENDING,
            created_at=datetime.now(timezone.utc).isoformat(),
            meta=meta or {},
            output_dir=output_dir,
        )
        self._save(job)
        self._log_path(job_id).touch(exist_ok=True)
        return job

    def get(self, job_id: str) -> Optional[JobRecord]:
        return self._load(job_id)

    def start(self, job_id: str) -> None:
        current_job_id.set(job_id)
        job = self._load(job_id)
        if job:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc).isoformat()
            self._save(job)

    def complete(self, job_id: str, exit_code: int = 0, results: Any = None) -> None:
        job = self._load(job_id)
        if job:
            job.status = JobStatus.COMPLETED if exit_code == 0 else JobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.results = results
            if exit_code != 0:
                job.error = f"Process exited with code {exit_code}"
            self._save(job)

    def fail(self, job_id: str, error: str) -> None:
        job = self._load(job_id)
        if job:
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.error = error
            self._save(job)

    def log(self, job_id: str, line: str) -> None:
        """Append a line to the job's log file."""
        with self._lock:
            with open(self._log_path(job_id), "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def get_logs(self, job_id: str, tail: Optional[int] = None) -> list[str]:
        p = self._log_path(job_id)
        if not p.exists():
            return []
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        if tail:
            return lines[-tail:]
        return lines

    def list_all(self) -> list[JobRecord]:
        jobs = []
        for p in self.jobs_dir.glob("*.json"):
            try:
                j = JobRecord.model_validate_json(p.read_text())
                jobs.append(j)
            except Exception:
                continue
        # Sort by created_at descending
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs

    def cancel(self, job_id: str) -> bool:
        job = self._load(job_id)
        if not job:
            return False
            
        job.status = JobStatus.CANCELED
        job.finished_at = datetime.now(timezone.utc).isoformat()
        job.error = "Canceled by user"
        self._save(job)
        
        # Clean up any running containers for this job
        try:
            import subprocess
            from bimos.infrastructure.container import _detect_runtime, _get_proc_env
            runtime = _detect_runtime()
            proc_env = _get_proc_env()
            res = subprocess.run(
                [runtime, "ps", "-q", "--filter", f"label=bimos_job_id={job_id}"],
                capture_output=True, text=True, env=proc_env
            )
            cids = res.stdout.strip().split()
            if cids:
                subprocess.run([runtime, "rm", "-f"] + cids, env=proc_env)
        except Exception:
            pass
            
        return True

    def delete(self, job_id: str) -> bool:
        p = self._path(job_id)
        log_p = self._log_path(job_id)
        deleted = False
        with self._lock:
            if p.exists():
                p.unlink()
                deleted = True
            if log_p.exists():
                log_p.unlink()
                
        # Clean up any running containers for this job
        try:
            import subprocess
            from bimos.infrastructure.container import _detect_runtime, _get_proc_env
            runtime = _detect_runtime()
            proc_env = _get_proc_env()
            res = subprocess.run(
                [runtime, "ps", "-q", "--filter", f"label=bimos_job_id={job_id}"],
                capture_output=True, text=True, env=proc_env
            )
            cids = res.stdout.strip().split()
            if cids:
                subprocess.run([runtime, "rm", "-f"] + cids, env=proc_env)
        except Exception:
            pass

        return deleted

# Singleton instance
store = FileJobStore()
