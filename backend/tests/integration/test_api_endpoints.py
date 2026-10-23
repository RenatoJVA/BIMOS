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


def test_system_theme_removed(client: TestClient) -> None:
    # /system/theme was removed: the frontend resolves themes via matchMedia.
    response = client.get("/api/v1/system/theme")
    assert response.status_code == 404


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


def test_ligands_endpoints_are_registered(client: TestClient) -> None:
    paths = client.get("/openapi.json").json()["paths"]
    assert "/api/v1/ligands" in paths
    assert "/api/v1/ligands/{cid}" in paths


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

    with patch("bimos.api.endpoints.dock.store", fake_store), patch("bimos.api.utils.store", fake_store):
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


def test_predict_endpoint_with_num_models(client: TestClient, tmp_path: Path, monkeypatch) -> None:
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
                    "num_models": 3,
                },
            )
            assert response.status_code == 202


def _temp_store(tmp_path: Path):
    from bimos.infrastructure.job_store import FileJobStore

    store = FileJobStore()
    store.jobs_dir = tmp_path / ".jobs"
    store.jobs_dir.mkdir(parents=True, exist_ok=True)
    return store


def test_stream_logs_replays_from_offset_and_closes(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    store = _temp_store(tmp_path)
    job = store.create(kind="dock")
    store.log(job.id, "line-1")
    store.log(job.id, "line-2")
    store.complete(job.id, exit_code=0)
    monkeypatch.setattr("bimos.api.endpoints.jobs.store", store)
    monkeypatch.setattr("bimos.api.utils.store", store)

    response = client.get(f"/api/v1/jobs/{job.id}/logs/stream")
    assert response.status_code == 200
    assert "line-1" in response.text
    assert "line-2" in response.text
    assert '"status": "completed"' in response.text

    offset = len("line-1\n")
    response = client.get(f"/api/v1/jobs/{job.id}/logs/stream", params={"offset": offset})
    assert "line-1" not in response.text
    assert "line-2" in response.text


def test_cancel_terminal_job_returns_conflict(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    store = _temp_store(tmp_path)
    job = store.create(kind="dock")
    store.start(job.id)
    store.complete(job.id, exit_code=0)
    monkeypatch.setattr("bimos.api.endpoints.jobs.store", store)
    monkeypatch.setattr("bimos.api.utils.store", store)

    response = client.post(f"/api/v1/jobs/{job.id}/cancel")
    assert response.status_code == 409
    assert store.get(job.id).status.value == "completed"


def test_dock_rejects_oversized_upload(client: TestClient, tmp_path: Path, monkeypatch) -> None:
    from bimos.api import utils as api_utils
    from bimos.config.settings import settings as bimos_settings

    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    monkeypatch.setattr(api_utils, "MAX_UPLOAD_BYTES", 8)

    response = client.post(
        "/api/v1/dock",
        files={
            "protein": ("test.pdb", b"ATG" * 20, "application/octet"),
            "ligands": ("ligands.sdf", b"ligand data", "chemical/x-mdl-sdfile"),
        },
    )
    assert response.status_code == 413


def test_job_result_files_list_download_and_traversal(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    from bimos.config.settings import settings as bimos_settings
    from bimos.infrastructure.job_store import store

    monkeypatch.setattr(bimos_settings, "workspace_path", tmp_path)
    root = tmp_path / "md-result"
    root.mkdir()
    (root / "final.pdb").write_text("ATOM      1  N   ALA A   1\n", encoding="utf-8")
    (root / "traj.trr").write_bytes(b"TRR\x00binary")
    job = store.create("md", output_dir=str(root))
    try:
        listed = client.get(f"/api/v1/jobs/{job.id}/files")
        assert listed.status_code == 200
        paths = {item["path"] for item in listed.json()["files"]}
        assert paths == {"final.pdb", "traj.trr"}

        pdb = client.get(f"/api/v1/jobs/{job.id}/files/final.pdb")
        assert pdb.status_code == 200
        assert pdb.headers["content-type"].startswith("chemical/x-pdb")
        assert b"ATOM" in pdb.content

        trr = client.get(f"/api/v1/jobs/{job.id}/files/traj.trr")
        assert trr.status_code == 200
        assert trr.content == b"TRR\x00binary"

        traversal = client.get(f"/api/v1/jobs/{job.id}/files/..%2F..%2Fetc%2Fpasswd")
        assert traversal.status_code == 404
    finally:
        store.delete(job.id)


def test_job_result_files_rejects_output_outside_workspace(
    client: TestClient, tmp_path: Path, monkeypatch
) -> None:
    from bimos.config.settings import settings as bimos_settings
    from bimos.infrastructure.job_store import store

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setattr(bimos_settings, "workspace_path", workspace)
    job = store.create("md", output_dir=str(outside))
    try:
        response = client.get(f"/api/v1/jobs/{job.id}/files")
        assert response.status_code == 403
    finally:
        store.delete(job.id)
