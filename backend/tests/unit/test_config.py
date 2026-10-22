import os
import subprocess
import sys
from pathlib import Path

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
    monkeypatch.setattr("bimos.config.settings.Settings._physical_core_count", lambda _: 12)
    s = Settings()
    s.max_threads = False
    assert s.get_threads() == 4


def test_settings_get_threads_max(monkeypatch) -> None:
    monkeypatch.setattr("bimos.config.settings.Settings._physical_core_count", lambda _: 12)
    s = Settings()
    s.max_threads = True
    assert s.get_threads() == 12


def test_settings_get_threads_single_cpu(monkeypatch) -> None:
    monkeypatch.setattr("bimos.config.settings.Settings._physical_core_count", lambda _: 1)
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

def _isolated_env(tmp_path: Path) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("BIMOS_") and key not in {"ORCA_PATH", "GAUSSIAN_PATH"}
    }
    env["BIMOS_BASE_PATH"] = str(tmp_path)
    return env


def test_import_does_not_create_user_config(tmp_path: Path) -> None:
    """Importing settings must not write ~/.bimos or print a welcome banner."""
    backend = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", "import bimos.config.settings"],
        cwd=backend,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not (tmp_path / ".env").exists()
    assert not (tmp_path / "config").exists()
    assert "Welcome to BIMOS" not in result.stderr


def test_initialize_creates_and_loads_user_config(tmp_path: Path) -> None:
    backend = Path(__file__).resolve().parents[2]
    code = (
        "from bimos.config.settings import BIMOS_BASE, BIMOS_ENV_FILE, initialize, settings\n"
        "created = initialize(announce=False)\n"
        "assert created is True\n"
        "assert BIMOS_ENV_FILE.exists()\n"
        "assert settings.workspace_path == BIMOS_BASE / 'workspace'\n"
        "assert settings.cache_path == BIMOS_BASE / 'cache'\n"
        "assert initialize(announce=False) is False\n"
    )
    result = subprocess.run(  # noqa: S603 - fixed argv, trusted interpreter
        [sys.executable, "-c", code],
        cwd=backend,
        env=_isolated_env(tmp_path),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / ".env").exists()
    assert (tmp_path / "config" / "docking.yaml").exists()
    assert "Welcome to BIMOS" not in result.stderr
