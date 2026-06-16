import json
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

from bimos.infrastructure.job_store import FileJobStore, JobRecord, JobStatus


@pytest.fixture
def store(tmp_workspace: Path) -> FileJobStore:
    s = FileJobStore()
    s.jobs_dir = tmp_workspace / ".jobs"
    s.jobs_dir.mkdir(parents=True, exist_ok=True)
    return s


def test_create_job(store: FileJobStore) -> None:
    job = store.create(kind="dock", meta={"protein": "test.pdb"})
    assert job.id
    assert job.kind == "dock"
    assert job.status == JobStatus.PENDING
    assert job.meta == {"protein": "test.pdb"}
    assert store.get(job.id) is not None


def test_create_and_retrieve(store: FileJobStore) -> None:
    job = store.create(kind="predict", output_dir="/tmp/output")
    retrieved = store.get(job.id)
    assert retrieved is not None
    assert retrieved.id == job.id
    assert retrieved.kind == "predict"
    assert retrieved.output_dir == "/tmp/output"


def test_get_nonexistent_returns_none(store: FileJobStore) -> None:
    assert store.get("nonexistent") is None


def test_start_job(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    store.start(job.id)
    retrieved = store.get(job.id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.RUNNING
    assert retrieved.started_at is not None


def test_complete_job_success(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    store.start(job.id)
    store.complete(job.id, exit_code=0, results={"score": -7.5})
    retrieved = store.get(job.id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.COMPLETED
    assert retrieved.results == {"score": -7.5}
    assert retrieved.finished_at is not None


def test_complete_job_failure(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    store.start(job.id)
    store.complete(job.id, exit_code=1)
    retrieved = store.get(job.id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.FAILED
    assert retrieved.error == "Process exited with code 1"


def test_fail_job(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    store.start(job.id)
    store.fail(job.id, "Something went wrong")
    retrieved = store.get(job.id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.FAILED
    assert "Something went wrong" in retrieved.error


def test_cancel_job(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    store.start(job.id)
    result = store.cancel(job.id)
    assert result is True
    retrieved = store.get(job.id)
    assert retrieved is not None
    assert retrieved.status == JobStatus.CANCELED


def test_cancel_nonexistent_returns_false(store: FileJobStore) -> None:
    result = store.cancel("nonexistent")
    assert result is False


def test_delete_job(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    assert store.get(job.id) is not None
    deleted = store.delete(job.id)
    assert deleted is True
    assert store.get(job.id) is None


def test_delete_nonexistent_returns_false(store: FileJobStore) -> None:
    deleted = store.delete("nonexistent")
    assert deleted is False


def test_list_all(store: FileJobStore) -> None:
    j1 = store.create(kind="dock")
    j2 = store.create(kind="predict")
    j3 = store.create(kind="simulate")
    all_jobs = store.list_all()
    ids = [j.id for j in all_jobs]
    assert j1.id in ids
    assert j2.id in ids
    assert j3.id in ids
    assert len(all_jobs) >= 3


def test_log_and_get_logs(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    store.log(job.id, "Step 1: Preparing receptor")
    store.log(job.id, "Step 2: Running docking")
    store.log(job.id, "Step 3: Done")
    logs = store.get_logs(job.id)
    assert len(logs) == 3
    assert logs[0] == "Step 1: Preparing receptor"


def test_logs_tail(store: FileJobStore) -> None:
    job = store.create(kind="dock")
    for i in range(10):
        store.log(job.id, f"Line {i}")
    tail = store.get_logs(job.id, tail=3)
    assert len(tail) == 3
    assert tail[-1] == "Line 9"


def test_get_logs_nonexistent(store: FileJobStore) -> None:
    assert store.get_logs("nonexistent") == []


def test_job_record_serialization() -> None:
    record = JobRecord(
        id="test-1",
        kind="dock",
        status=JobStatus.RUNNING,
        created_at="2026-01-01T00:00:00",
    )
    data = record.model_dump_json()
    parsed = JobRecord.model_validate_json(data)
    assert parsed.id == "test-1"
    assert parsed.status == JobStatus.RUNNING


def test_concurrent_complete_no_race(tmp_path: Path) -> None:
    from bimos.infrastructure.job_store import FileJobStore
    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)
    j1 = store.create("dock")
    j2 = store.create("dock")
    store.start(j1.id)
    store.start(j2.id)

    def complete_job1():
        store.complete(j1.id, exit_code=0)

    def complete_job2():
        store.complete(j2.id, exit_code=0)

    t1 = threading.Thread(target=complete_job1)
    t2 = threading.Thread(target=complete_job2)
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    assert store.get(j1.id).status == JobStatus.COMPLETED
    assert store.get(j2.id).status == JobStatus.COMPLETED


def test_cancel_can_override_completed(tmp_path: Path) -> None:
    from bimos.infrastructure.job_store import FileJobStore
    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)
    job = store.create("dock")
    store.start(job.id)
    store.complete(job.id, exit_code=0)
    store.cancel(job.id)
    assert store.get(job.id).status == JobStatus.CANCELED


def test_atomic_write_survives_crash(tmp_path: Path) -> None:
    from bimos.infrastructure.job_store import FileJobStore
    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)
    job = store.create("dock")
    store.start(job.id)
    job_path = store._path(job.id)
    tmp = job_path.with_suffix(".tmp")
    tmp.write_text("invalid json")
    assert job_path.exists()
    data = json.loads(job_path.read_text())
    assert data["status"] == "running"


def test_list_all_empty(store: FileJobStore) -> None:
    jobs = store.list_all()
    assert jobs == []


def test_start_nonexistent_does_not_raise(store: FileJobStore) -> None:
    store.start("nonexistent")


def test_complete_nonexistent_does_not_raise(store: FileJobStore) -> None:
    store.complete("nonexistent", exit_code=0)
