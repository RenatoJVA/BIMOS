import os
from pathlib import Path
from unittest.mock import patch

import pytest

from bimos.config.settings import Settings


@pytest.fixture(autouse=True)
def _reset_settings():
    yield


def test_settings_defaults() -> None:
    s = Settings()
    assert s.app_name == "BIMOS"
    assert s.app_version == "0.1.0"


def test_settings_host_port() -> None:
    s = Settings()
    assert s.host == "127.0.0.1"
    assert s.port == 8000


def test_settings_get_threads_default(monkeypatch) -> None:
    monkeypatch.setattr("bimos.config.settings.os.cpu_count", lambda: 12)
    s = Settings()
    s.max_threads = False
    assert s.get_threads() == 4


def test_settings_get_threads_max(monkeypatch) -> None:
    monkeypatch.setattr("bimos.config.settings.os.cpu_count", lambda: 12)
    s = Settings()
    s.max_threads = True
    assert s.get_threads() == 12


def test_settings_get_threads_single_cpu(monkeypatch) -> None:
    monkeypatch.setattr("bimos.config.settings.os.cpu_count", lambda: 1)
    s = Settings()
    s.max_threads = False
    assert s.get_threads() == 1


def test_settings_use_gpu_property() -> None:
    s = Settings()
    assert isinstance(s.use_gpu, bool)


def test_settings_container_runtime(monkeypatch) -> None:
    def mock_which(name: str) -> str | None:
        if name == "podman":
            return "/usr/bin/podman"
        return None

    monkeypatch.setattr("bimos.config.settings.shutil.which", mock_which)
    assert Settings.container_runtime() == "podman"


def test_settings_container_runtime_fallback(monkeypatch) -> None:
    def mock_which(name: str) -> str | None:
        if name == "docker":
            return "/usr/bin/docker"
        return None

    monkeypatch.setattr("bimos.config.settings.shutil.which", mock_which)
    assert Settings.container_runtime() == "docker"


def test_settings_container_runtime_not_found(monkeypatch) -> None:
    monkeypatch.setattr("bimos.config.settings.shutil.which", lambda x: None)
    with pytest.raises(RuntimeError, match="No container runtime found"):
        Settings.container_runtime()


def test_settings_orca_path(monkeypatch) -> None:
    monkeypatch.setenv("ORCA_PATH", "/usr/local/orca/orca")
    s = Settings()
    assert s.orca_path == "/usr/local/orca/orca"


def test_settings_gaussian_path(monkeypatch) -> None:
    monkeypatch.setenv("GAUSSIAN_PATH", "/usr/local/g16/g16")
    s = Settings()
    assert s.gaussian_path == "/usr/local/g16/g16"


def test_settings_ensure_dirs(tmp_path: Path) -> None:
    s = Settings()
    s.workspace_path = tmp_path / "workspace"
    s.cache_path = tmp_path / "cache"
    s.logs_path = tmp_path / "logs"
    s.ensure_dirs()
    assert (tmp_path / "workspace").exists()
    assert (tmp_path / "cache").exists()
    assert (tmp_path / "logs").exists()


def test_settings_bimos_image_default() -> None:
    s = Settings()
    assert isinstance(s.bimos_image, str)


def test_settings_cache_path_default() -> None:
    s = Settings()
    assert s.cache_path is not None
