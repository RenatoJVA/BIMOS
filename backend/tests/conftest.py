import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def clean_env() -> None:
    saved = dict(os.environ)
    os.environ.setdefault("BIMOS_WORKSPACE", "/tmp/bimos_test_ws")
    os.environ.setdefault("BIMOS_CACHE", "/tmp/bimos_test_cache")
    os.environ.setdefault("BIMOS_LOGS", "/tmp/bimos_test_logs")
    os.environ.setdefault("BIMOS_IMAGE", "localhost/bimos/test:latest")
    os.environ.setdefault("BIMOS_USE_GPU", "false")
    os.environ.setdefault("ORCA_PATH", "")
    os.environ.setdefault("GAUSSIAN_PATH", "")
    os.environ.setdefault("BIMOS_DATABASE_URL", "sqlite:///test_bimos.db")
    os.environ.setdefault("BIMOS_BASE_PATH", "/tmp/bimos_test_base")
    yield
    os.environ.clear()
    os.environ.update(saved)


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "workspace"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "jobs").mkdir(exist_ok=True)
    (ws / "log").mkdir(exist_ok=True)
    (ws / ".jobs").mkdir(exist_ok=True)
    return ws


@pytest.fixture
def sample_receptor() -> Path:
    p = Path("tests/fixtures/sample_receptor.pdb")
    if not p.exists():
        p = Path(__file__).parent / "fixtures" / "sample_receptor.pdb"
    return p


@pytest.fixture
def sample_ligands() -> Path:
    p = Path("tests/fixtures/sample_ligand.sdf")
    if not p.exists():
        p = Path(__file__).parent / "fixtures" / "sample_ligand.sdf"
    return p


@pytest.fixture
def sample_fasta() -> str:
    return ">test\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG"


@pytest.fixture
def sample_fasta_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.fasta"
    p.write_text(">test\nMQIFVKTLTGKTITLEVEPSDTIENVKAKIQDKEGIPPDQQRLIFAGKQLEDGRTLSDYNIQKESTLHLVLRLRGG")
    return p


@pytest.fixture
def sample_config_yaml_path(tmp_path: Path) -> Path:
    p = tmp_path / "test_config.yaml"
    p.write_text("app_name: BIMOS\napp_version: 0.1.0\ndebug: false\n")
    return p


@pytest.fixture
def sample_job_store_json(tmp_path: Path) -> Path:
    p = tmp_path / "sample_job_store.json"
    data = {
        "id": "abc123",
        "kind": "dock",
        "status": "completed",
        "created_at": "2026-06-14T10:00:00+00:00",
        "started_at": "2026-06-14T10:00:05+00:00",
        "finished_at": "2026-06-14T10:05:30+00:00",
        "error": None,
        "output_dir": "/tmp/bimos_test_ws/docking/test",
        "meta": {"protein": "test.pdb", "ligands": "test.sdf"},
        "results": {"status": "completed", "scores": [-7.5, -6.2]},
    }
    p.write_text(json.dumps(data, indent=2))
    return p


@pytest.fixture
def mock_container():
    from tests.mocks.container_mock import ContainerMock

    mock = ContainerMock()
    with patch("bimos.infrastructure.container.run", mock.run):
        with patch("bimos.infrastructure.container.image_exists", mock.image_exists):
            yield mock


@pytest.fixture
def mock_container_build():
    from tests.mocks.container_mock import ContainerMock

    mock = ContainerMock()
    with patch("bimos.infrastructure.container.run", mock.run):
        with patch("bimos.infrastructure.container.image_exists", mock.image_exists):
            with patch("bimos.infrastructure.container.build_image", mock.build_image):
                yield mock


@pytest.fixture
def mock_subprocess():
    from unittest.mock import MagicMock, patch

    mock = MagicMock()
    mock.returncode = 0
    mock.stdout = "mock output"
    mock.stderr = ""
    with patch("subprocess.run", return_value=mock):
        with patch("subprocess.Popen") as mock_popen:
            proc_mock = MagicMock()
            proc_mock.stdout = ["line1\n", "line2\n"]
            proc_mock.wait.return_value = 0
            proc_mock.returncode = 0
            proc_mock.pid = 12345
            mock_popen.return_value = proc_mock
            yield mock_popen


@pytest.fixture
def mock_settings(monkeypatch, tmp_path):
    monkeypatch.setattr("bimos.config.settings.workspace_path", tmp_path / "workspace")
    monkeypatch.setattr("bimos.config.settings.cache_path", tmp_path / "cache")
    monkeypatch.setattr("bimos.config.settings.logs_path", tmp_path / "logs")
    monkeypatch.setattr("bimos.config.settings.bimos_image", "localhost/bimos/test:latest")
    monkeypatch.setattr("bimos.config.settings.use_gpu", False)
    monkeypatch.setattr("bimos.config.settings.max_threads", False)

    def mock_get_threads():
        return 4

    monkeypatch.setattr("bimos.config.settings.get_threads", mock_get_threads)

    def mock_container_runtime():
        return "podman"

    monkeypatch.setattr("bimos.config.settings.container_runtime", mock_container_runtime)


@pytest.fixture(autouse=True)
def ensure_test_fixtures_dir():
    fixtures_dir = Path(__file__).parent / "fixtures"
    fixtures_dir.mkdir(parents=True, exist_ok=True)
    return fixtures_dir
