"""Centralized configuration for BIMOS."""

import os
import sys
import shutil
from importlib import resources
from pathlib import Path
from dotenv import load_dotenv

from bimos.shared.paths import DEFAULTS_DIR

BIMOS_BASE = (
    Path(os.getenv("BIMOS_BASE_PATH", Path.home() / ".bimos")).expanduser().resolve()
)
BIMOS_ENV_FILE = BIMOS_BASE / ".env"


PROCESS_CONFIG_FILES = (
    "docking",
    "md",
    "esmfold",
    "boltz",
    "orca",
    "gaussian",
)


def _render_env_template() -> str:
    """Build the initial ``.env`` file from the packaged template."""
    template_path = DEFAULTS_DIR / "env.template"
    if template_path.exists():
        text = template_path.read_text(encoding="utf-8")
    else:
        text = (
            resources.files("bimos.config.defaults")
            .joinpath("env.template")
            .read_text(encoding="utf-8")
        )
    replacements = {
        "${BIMOS_WORKSPACE}": (BIMOS_BASE / "workspace").as_posix(),
        "${BIMOS_CACHE}": (BIMOS_BASE / "cache").as_posix(),
        "${BIMOS_LOGS}": (BIMOS_BASE / "logs").as_posix(),
        "${BIMOS_ESM_CACHE}": (BIMOS_BASE / "cache" / "esm").as_posix(),
    }
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def _bootstrap_user_configs() -> None:
    config_dir = BIMOS_BASE / "config"
    config_dir.mkdir(parents=True, exist_ok=True)

    for name in PROCESS_CONFIG_FILES:
        target = config_dir / f"{name}.yaml"
        if target.exists():
            continue
        packaged = DEFAULTS_DIR / f"{name}.yaml"
        if packaged.exists():
            shutil.copy2(packaged, target)
        else:
            resource = resources.files("bimos.config.defaults").joinpath(
                f"{name}.yaml"
            )
            target.write_text(resource.read_text(encoding="utf-8"), encoding="utf-8")


def _bootstrap_first_run() -> None:
    """Create .env and config files on first run. Then reload."""
    BIMOS_BASE.mkdir(parents=True, exist_ok=True)
    BIMOS_ENV_FILE.write_text(_render_env_template(), encoding="utf-8")
    _bootstrap_user_configs()
    print(
        "============================================================", file=sys.stderr
    )
    print(
        " Welcome to BIMOS! A default configuration has been created:", file=sys.stderr
    )
    print(f"   {BIMOS_ENV_FILE}", file=sys.stderr)
    print(
        " Please edit this file to configure your workspace and paths.", file=sys.stderr
    )
    print(" Per-process YAML configs will be created in:", file=sys.stderr)
    print(f"   {BIMOS_BASE / 'config'}", file=sys.stderr)
    print(" Then launch the software again.", file=sys.stderr)
    print(
        "============================================================", file=sys.stderr
    )


_initialized = False


def _ensure_initialized() -> None:
    global _initialized
    if _initialized:
        return
    if not BIMOS_ENV_FILE.exists():
        _bootstrap_first_run()
    load_dotenv(BIMOS_ENV_FILE)
    _initialized = True


_ensure_initialized()


class Settings:
    # Application
    app_name: str = "BIMOS"
    app_version: str = "0.1.0"
    debug: bool = os.getenv("BIMOS_DEBUG", "false").lower() == "true"

    # Server
    host: str = os.getenv("BIMOS_HOST", "127.0.0.1")
    port: int = int(os.getenv("BIMOS_PORT", "8000"))

    # Paths
    base_path: Path = BIMOS_BASE
    workspace_path: Path = (
        Path(os.getenv("BIMOS_WORKSPACE", str(BIMOS_BASE / "workspace")))
        .expanduser()
        .resolve()
    )
    cache_path: Path = (
        Path(os.getenv("BIMOS_CACHE", str(BIMOS_BASE / "cache"))).expanduser().resolve()
    )
    logs_path: Path = (
        Path(os.getenv("BIMOS_LOGS", str(BIMOS_BASE / "logs"))).expanduser().resolve()
    )

    # ESM model cache
    esm_cache_path: Path = (
        Path(os.getenv("BIMOS_ESM_CACHE", str(BIMOS_BASE / "cache" / "esm")))
        .expanduser()
        .resolve()
    )
    esm_model_url: str = "https://colabfold.steineggerlab.workers.dev/esm/esmfold.model"

    # Container image
    bimos_image: str = os.getenv("BIMOS_IMAGE", "localhost/bimos/global:latest")
    use_gpu: bool = os.getenv("BIMOS_USE_GPU", "true").lower() == "true"
    max_threads: bool = False

    # Remote Connection
    remote_url: str = os.getenv(
        "BIMOS_REMOTE_URL", ""
    )  # e.g., http://192.168.1.100:8000
    ssh_host: str = os.getenv("BIMOS_SSH_HOST", "")
    ssh_user: str = os.getenv("BIMOS_SSH_USER", "")
    ssh_key: str = os.getenv("BIMOS_SSH_KEY", "")

    def get_threads(self) -> int:
        """Calculate number of threads based on max_threads flag."""
        total = os.cpu_count() or 1
        if self.max_threads:
            return total
        return max(1, total // 3)

    # Container runtime: auto-detect podman > docker
    @staticmethod
    def container_runtime() -> str:
        if shutil.which("podman"):
            return "podman"
        if shutil.which("docker"):
            return "docker"
        raise RuntimeError(
            "No container runtime found. Install Podman or Docker and ensure it is in PATH."
        )

    # Database
    database_url: str = os.getenv(
        "BIMOS_DATABASE_URL", ""
    )

    # ORCA and Gaussian: defined by host binary path (not containerized)
    @property
    def orca_path(self) -> str:
        path = os.getenv("ORCA_PATH", "")
        if not path:
            return ""
        return os.path.expandvars(os.path.expanduser(path))

    @property
    def gaussian_path(self) -> str:
        path = os.getenv("GAUSSIAN_PATH", "")
        if not path:
            return ""
        return os.path.expandvars(os.path.expanduser(path))

    def ensure_dirs(self) -> None:
        """Create all required directories and user config files on first run."""
        for p in [
            self.base_path,
            self.workspace_path,
            self.cache_path,
            self.logs_path,
            self.esm_cache_path,
        ]:
            Path(p).mkdir(parents=True, exist_ok=True)

        from bimos.shared.user_config import ensure_user_configs

        ensure_user_configs()


settings = Settings()
