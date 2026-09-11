"""
Persistent, thread-safe Job Store for BIMOS.
Stores jobs as JSON files and logs as plain text in the workspace.
This allows multiple CLI processes and the GUI server to share the same state.
"""

import logging
import os
import threading
from contextvars import ContextVar
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from bimos.config.settings import settings
from bimos.infrastructure import cancellation

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
    started_at: str | None = None
    finished_at: str | None = None
    error: str | None = None
    output_dir: str | None = None
    meta: dict[str, Any] = {}
    results: Any | None = None


class FileJobStore:
    def __init__(self) -> None:
        self.jobs_dir = settings.workspace_path / ".jobs"
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._log_buffers: dict[str, list[str]] = {}
        self._log_buffer_size = 64
        self._list_cache: list[JobRecord] | None = None
        self._list_cache_stamp: tuple[int, int] | None = None

    def _path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.json"

    def _log_path(self, job_id: str) -> Path:
        return self.jobs_dir / f"{job_id}.log"

    def _save_unlocked(self, job: JobRecord) -> None:
        p = self._path(job.id)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(job.model_dump_json(indent=2))
        tmp.rename(p)
        self._list_cache = None

    def _load(self, job_id: str) -> JobRecord | None:
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
            created_at=datetime.now(UTC).isoformat(),
            meta=meta or {},
            output_dir=output_dir,
        )
        with self._lock:
            self._save_unlocked(job)
        self._log_path(job_id).touch(exist_ok=True)
        return job

    def get(self, job_id: str) -> JobRecord | None:
        return self._load(job_id)

    def start(self, job_id: str) -> None:
        with self._lock:
            current_job_id.set(job_id)
            job = self._load(job_id)
            if job is None or job.status != JobStatus.PENDING:
                return
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(UTC).isoformat()
            self._save_unlocked(job)

    def complete(self, job_id: str, exit_code: int = 0, results: Any = None) -> None:
        with self._lock:
            job = self._load(job_id)
            if job is None:
                return
            job.status = JobStatus.COMPLETED if exit_code == 0 else JobStatus.FAILED
            job.finished_at = datetime.now(UTC).isoformat()
            if exit_code == 0:
                job.results = results
            else:
                job.error = f"Process exited with code {exit_code}"
            self._save_unlocked(job)
        self.flush(job_id)

    def fail(self, job_id: str, error: str) -> None:
        with self._lock:
            job = self._load(job_id)
            if job is None:
                return
            job.status = JobStatus.FAILED
            job.finished_at = datetime.now(UTC).isoformat()
            job.error = error
            self._save_unlocked(job)
        self.flush(job_id)

    def log(self, job_id: str, line: str) -> None:
        """Buffer a log line, flushing to disk once the buffer fills."""
        with self._lock:
            buf = self._log_buffers.get(job_id)
            if buf is None:
                buf = []
                self._log_buffers[job_id] = buf
            buf.append(line)
            if len(buf) >= self._log_buffer_size:
                self._flush_buffer(job_id, buf)

    def _flush_buffer(self, job_id: str, buf: list[str]) -> None:
        if not buf:
            return
        path = self._log_path(job_id)
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n".join(buf) + "\n")
        finally:
            buf.clear()

    def flush(self, job_id: str) -> None:
        """Flush any buffered log lines for a job to disk."""
        with self._lock:
            buf = self._log_buffers.get(job_id)
            if buf:
                self._flush_buffer(job_id, buf)

    def get_logs(self, job_id: str, tail: int | None = None) -> list[str]:
        self.flush(job_id)
        p = self._log_path(job_id)
        if not p.exists():
            return []
        try:
            if tail is not None and tail > 0:
                return self._tail_lines_fast(p, tail)
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        if tail:
            return lines[-tail:]
        return lines

    @staticmethod
    def _tail_lines_fast(path: Path, n: int) -> list[str]:
        """Return the last *n* lines reading only the end of the file."""
        try:
            with open(path, "rb") as f:
                f.seek(0, 2)
                size = f.tell()
                chunk_size = min(size, 8192)
                lines: list[str] = []
                offset = size
                # Scan backwards until we have n lines or reach the start.
                while offset > 0 and len(lines) < n:
                    read_start = max(0, offset - chunk_size)
                    read_end = offset
                    f.seek(read_start)
                    data = f.read(read_end - read_start).decode("utf-8", errors="replace")
                    chunk_lines = data.splitlines()
                    new_lines = chunk_lines[0:-1] if read_start > 0 else data.splitlines()
                    lines = new_lines + lines
                    offset = read_start
                return lines[-n:]
        except OSError:
            return []

    def tail_log(self, job_id: str, n: int = 10) -> list[str]:
        """Return the last *n* lines of a job's log efficiently (reads from end)."""
        self.flush(job_id)
        return self._tail_lines_fast(self._log_path(job_id), n)

    def list_all(self) -> list[JobRecord]:
        self._maybe_invalidate_list_cache()
        if self._list_cache is not None:
            return self._list_cache
        jobs = []
        for p in self.jobs_dir.glob("*.json"):
            try:
                j = JobRecord.model_validate_json(p.read_text())
                jobs.append(j)
            except Exception:
                continue
        jobs.sort(key=lambda x: x.created_at, reverse=True)
        self._list_cache = jobs
        return jobs

    def _maybe_invalidate_list_cache(self) -> None:
        """Rebuild the list cache only when the jobs directory content changed."""
        try:
            stamp = (len(list(self.jobs_dir.glob("*.json"))), self.jobs_dir.stat().st_mtime_ns)
        except OSError:
            return
        if stamp != self._list_cache_stamp:
            self._list_cache_stamp = stamp
            self._list_cache = None

    def cancel(self, job_id: str) -> bool:
        with self._lock:
            job = self._load(job_id)
            if not job:
                return False
            job.status = JobStatus.CANCELED
            job.finished_at = datetime.now(UTC).isoformat()
            job.error = "Canceled by user"
            self._save_unlocked(job)

        # Signal any in-flight pipeline code so it aborts promptly.
        cancellation.request(job_id)

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
                subprocess.run([runtime, "rm", "-f", *cids], env=proc_env)
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
            self._log_buffers.pop(job_id, None)
            self._list_cache = None
        cancellation.unregister(job_id)

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
                subprocess.run([runtime, "rm", "-f", *cids], env=proc_env)
        except Exception:
            pass

        return deleted

# Singleton instance
store = FileJobStore()
