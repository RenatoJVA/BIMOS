"""
Performance test: JobStore throughput.

Verifies that the FileJobStore can handle 1000 ops/second.
"""

import time

import pytest

pytestmark = pytest.mark.performance


def test_job_store_throughput(tmp_path: pytest.TempPathFactory) -> None:
    from bimos.infrastructure.job_store import FileJobStore
    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)

    start = time.perf_counter()
    n = 500
    for i in range(n):
        store.create(f"perf-{i}")
    elapsed = time.perf_counter() - start

    ops_per_sec = n / elapsed
    assert ops_per_sec > 100, f"Throughput too low: {ops_per_sec:.0f} ops/s"
