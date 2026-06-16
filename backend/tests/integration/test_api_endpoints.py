import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from bimos.api.server import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_system_theme(client: TestClient) -> None:
    response = client.get("/api/v1/system/theme")
    assert response.status_code == 200
    assert "theme" in response.json()


def test_list_jobs_empty(client: TestClient) -> None:
    response = client.get("/api/v1/jobs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_job_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/nonexistent")
    assert response.status_code == 404


def test_get_job_logs_not_found(client: TestClient) -> None:
    response = client.get("/api/v1/jobs/nonexistent/logs")
    assert response.status_code == 404


def test_cancel_job_not_found(client: TestClient) -> None:
    response = client.post("/api/v1/jobs/nonexistent/cancel")
    assert response.status_code == 404


def test_delete_job_not_found(client: TestClient) -> None:
    response = client.delete("/api/v1/jobs/nonexistent")
    assert response.status_code == 404


def test_config_profiles(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    monkeypatch.setattr(bimos_settings, "base_path", tmp_path / "bimos_test_base")
    from bimos.shared import user_config
    monkeypatch.setattr(user_config.settings, "base_path", tmp_path / "bimos_test_base")
    response = client.get("/api/v1/config/profiles")
    assert response.status_code == 200
    data = response.json()
    assert "config_dir" in data
    assert "processes" in data


def test_root_endpoint(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code in (200, 404)
    if response.headers.get("content-type", "").startswith("application/json"):
        data = response.json()
        assert "name" in data


def test_predict_endpoint_validation(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "test123"
    fake_job.kind = "predict"
    fake_job.status = "pending"
    fake_job.created_at = "2026-01-01T00:00:00"
    fake_job.started_at = None
    fake_job.finished_at = None
    fake_job.error = None
    fake_job.output_dir = ""
    fake_job.meta = {}
    fake_job.results = None
    fake_store.create.return_value = fake_job
    fake_store.get.return_value = fake_job

    with patch("bimos.api.endpoints.predict.store", fake_store):
        with patch("bimos.api.utils.store", fake_store):
            response = client.post(
                "/api/v1/predict",
                json={
                    "fasta_content": ">test\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n",
                    "name": "test_protein",
                },
            )
            assert response.status_code == 202
            data = response.json()
            assert data["id"] == "test123"


def test_predict_boltz_endpoint(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "test456"
    fake_job.kind = "predict-boltz"
    fake_job.status = "pending"
    fake_job.created_at = "2026-01-01T00:00:00"
    fake_job.started_at = None
    fake_job.finished_at = None
    fake_job.error = None
    fake_job.output_dir = ""
    fake_job.meta = {}
    fake_job.results = None
    fake_store.create.return_value = fake_job
    fake_store.get.return_value = fake_job

    with patch("bimos.api.endpoints.predict.store", fake_store):
        with patch("bimos.api.utils.store", fake_store):
            response = client.post(
                "/api/v1/predict-boltz",
                json={
                    "fasta_content": ">test\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n",
                    "name": "test_protein",
                },
            )
            assert response.status_code == 202


def test_system_stats(client: TestClient, monkeypatch) -> None:
    import sys
    fake_psutil = MagicMock()
    fake_psutil.cpu_percent.return_value = 25.0
    fake_mem = MagicMock()
    fake_mem.percent = 50.0
    fake_psutil.virtual_memory.return_value = fake_mem

    monkeypatch.setitem(sys.modules, "psutil", fake_psutil)
    response = client.get("/api/v1/system/stats")
    assert response.status_code == 200
    data = response.json()
    assert "cpu" in data
    assert "memory" in data


def test_ligands_endpoint_no_db(client: TestClient, monkeypatch) -> None:
    with patch("bimos.infrastructure.database.search_ligands", side_effect=Exception("DB unavailable")):
        response = client.get("/api/v1/ligands?q=test")
        assert response.status_code == 503


def test_ligands_endpoint_empty(client: TestClient, monkeypatch) -> None:
    with patch("bimos.infrastructure.database.search_ligands", return_value=[]):
        response = client.get("/api/v1/ligands?q=nonexistent")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0


def test_dock_endpoint_validation(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "dock789"
    fake_job.kind = "dock"
    fake_job.status = "pending"
    fake_job.created_at = "2026-01-01T00:00:00"
    fake_job.started_at = None
    fake_job.finished_at = None
    fake_job.error = None
    fake_job.output_dir = ""
    fake_job.meta = {}
    fake_job.results = None
    fake_store.create.return_value = fake_job
    fake_store.get.return_value = fake_job

    with patch("bimos.api.endpoints.dock.store", fake_store):
        with patch("bimos.api.utils.store", fake_store):
            response = client.post(
                "/api/v1/dock",
                files={
                    "protein": ("test.pdb", b"ATOM data", "application/octet"),
                    "ligands": ("ligands.sdf", b"ligand data", "chemical/x-mdl-sdfile"),
                },
            )
            assert response.status_code == 202
            data = response.json()
            assert data["id"] == "dock789"


def test_config_profiles_preview_max(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    monkeypatch.setattr(bimos_settings, "base_path", tmp_path / "bimos_test_base")
    from bimos.shared import user_config
    monkeypatch.setattr(user_config.settings, "base_path", tmp_path / "bimos_test_base")
    response = client.get("/api/v1/config/profiles?preview_max=true")
    assert response.status_code == 200
    data = response.json()
    assert "processes" in data


def test_jobs_list_with_mocked_store(client: TestClient) -> None:
    fake_store = MagicMock()
    fake_store.list_all.return_value = []
    with patch("bimos.api.endpoints.jobs.store", fake_store):
        response = client.get("/api/v1/jobs")
        assert response.status_code == 200
        assert response.json() == []


def test_predict_endpoint_with_recycles(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.config.settings import settings as bimos_settings
    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    fake_store = MagicMock()
    fake_job = MagicMock()
    fake_job.id = "recycle999"
    fake_job.kind = "predict"
    fake_job.status = "pending"
    fake_job.created_at = "2026-01-01T00:00:00"
    fake_job.started_at = None
    fake_job.finished_at = None
    fake_job.error = None
    fake_job.output_dir = ""
    fake_job.meta = {}
    fake_job.results = None
    fake_store.create.return_value = fake_job
    fake_store.get.return_value = fake_job

    with patch("bimos.api.endpoints.predict.store", fake_store):
        with patch("bimos.api.utils.store", fake_store):
            response = client.post(
                "/api/v1/predict",
                json={
                    "fasta_content": ">test\nMKFLILFNILVSTLAFLSSSFAQVREIYHQHQHYINEQSSELKWHES\n",
                    "name": "test_recycles",
                    "num_recycles": 3,
                },
            )
            assert response.status_code == 202
