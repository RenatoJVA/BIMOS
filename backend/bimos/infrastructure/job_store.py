"""
Persistent, thread-safe Job Store for BIMOS.
Stores jobs as JSON files and logs as plain text in the workspace.
This allows multiple CLI processes and the GUI server to share the same state.
"""

import logging
import os
import threading
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel
from contextvars import ContextVar

from bimos.config.settings import settings

logger = logging.getLogger(__name__)

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

    def _save_unlocked(self, job: JobRecord) -> None:
        p = self._path(job.id)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(job.model_dump_json(indent=2))
        tmp.rename(p)

    def _load(self, job_id: str) -> Optional[JobRecord]:
        p = self._path(job_id)
        if not p.exists():
            return None
        try:
            return JobRecord.model_validate_json(p.read_text())
        except Exception as e:
            logger.warning("Corrupted job file: %s — %s: %s", p, type(e).__name__, e)
            return None

    def create(self, kind: str, meta: dict[str, Any] | None = None, output_dir: str = "") -> JobRecord:
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
        with self._lock:
            self._save_unlocked(job)
        self._log_path(job_id).touch(exist_ok=True)
        return job

    def get(self, job_id: str) -> Optional[JobRecord]:
        return self._load(job_id)

    def start(self, job_id: str) -> None:
        with self._lock:
            current_job_id.set(job_id)
            job = self._load(job_id)
            if job is None or job.status != JobStatus.PENDING:
                return
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc).isoformat()
            self._save_unlocked(job)

    def complete(self, job_id: str, exit_code: int = 0, results: Any = None) -> None:
        with self._lock:
            job = self._load(job_id)
            if job is None:
                return
            job.status = JobStatus.COMPLETED if exit_code == 0 else JobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc).isoformat()
            if exit_code == 0:
                job.results = results
            else:
                job.error = f"Process exited with code {exit_code}"
            self._save_unlocked(job)

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._load(job_id)
            if job is None:
                return
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.error = error
            self._save_unlocked(job)

    def log(self, job_id: str, line: str) -> None:
        """Append a line to the job's log file."""
        with self._lock:
            with open(self._log_path(job_id), "a", encoding="utf-8") as f:
                f.write(line + "\n")

    def get_logs(self, job_id: str, tail: Optional[int] = None) -> list[str]:
        p = self._log_path(job_id)
        if not p.exists():
            return []
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        if tail:
            return lines[-tail:]
        return lines

    def tail_log(self, job_id: str, n: int = 10) -> list[str]:
        """Return the last *n* lines of a job's log efficiently (reads from end)."""
        p = self._log_path(job_id)
        if not p.exists():
            return []
        try:
            with open(p, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                if size == 0:
                    return []
                chunk_size = min(size, 4096)
                f.seek(max(0, size - chunk_size))
                data = f.read(chunk_size).decode("utf-8", errors="replace")
                lines = data.splitlines()
                return lines[-n:]
        except OSError:
            return []

    def list_all(self) -> list[JobRecord]:
        jobs = []
        for p in self.jobs_dir.glob("*.json"):
            try:
                j = JobRecord.model_validate_json(p.read_text())
                jobs.append(j)
            except Exception:
                continue
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        return jobs

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._load(job_id)
            if not job:
                return False
            job.status = JobStatus.CANCELED
            job.finished_at = datetime.now(timezone.utc).isoformat()
            job.error = "Canceled by user"
            self._save_unlocked(job)
        
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
