"""
Performance test: API response times.

Verifies that key API endpoints respond within acceptable time limits.
"""

import time

import pytest
from fastapi.testclient import TestClient

from bimos.api.server import app

pytestmark = pytest.mark.performance


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_response_time(client: TestClient) -> None:
    start = time.perf_counter()
    for _ in range(50):
        response = client.get("/api/v1/health")
        assert response.status_code == 200
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / 50) * 1000
    assert avg_ms < 500, f"Average health response time too high: {avg_ms:.1f}ms"


def test_list_jobs_response_time(client: TestClient) -> None:
    start = time.perf_counter()
    for _ in range(20):
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
    elapsed = time.perf_counter() - start
    avg_ms = (elapsed / 20) * 1000
    assert avg_ms < 500, f"Average jobs list response time too high: {avg_ms:.1f}ms"
