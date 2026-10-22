"""Security and deployment-mode tests for the FastAPI surface."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bimos.api.security import ensure_safe_binding
from bimos.api.server import app
from bimos.config.settings import settings

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_safe_binding_allows_loopback() -> None:
    ensure_safe_binding("127.0.0.1")
    ensure_safe_binding("localhost")


def test_safe_binding_rejects_exposed_api_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "")
    with pytest.raises(RuntimeError, match="BIMOS_API_TOKEN"):
        ensure_safe_binding("0.0.0.0")  # noqa: S104


def test_safe_binding_rejects_whitespace_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "   ")
    with pytest.raises(RuntimeError, match="BIMOS_API_TOKEN"):
        ensure_safe_binding("0.0.0.0")  # noqa: S104


def test_safe_binding_accepts_exposed_api_with_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_token", "secret")
    ensure_safe_binding("0.0.0.0")  # noqa: S104


def test_token_is_required_when_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "api_token", "secret")

    assert client.get("/api/v1/jobs").status_code == 401
    assert client.get("/api/v1/health").status_code == 200

    response = client.get("/api/v1/jobs", headers={"Authorization": "Bearer secret"})
    assert response.status_code == 200


def test_execution_disabled_rejects_job_submission(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "execution_mode", "disabled")

    response = client.post(
        "/api/v1/predict",
        json={"fasta_content": ">x\nMKT", "name": "blocked"},
    )
    assert response.status_code == 503
    assert "execution is disabled" in response.json()["detail"].lower()


def test_compose_is_loopback_and_never_mounts_docker_socket() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")

    assert "docker.sock" not in compose
    assert '"127.0.0.1:8000:8000"' in compose
    assert "BIMOS_EXECUTION_MODE: disabled" in compose
    assert "BIMOS_API_TOKEN" in compose
