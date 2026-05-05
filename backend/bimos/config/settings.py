"""Centralized configuration for BIMOS."""

import os
import sys
import shutil
from pathlib import Path
from dotenv import load_dotenv

BIMOS_BASE = Path(os.getenv("BIMOS_BASE_PATH", Path.home() / ".bimos")).expanduser().resolve()
BIMOS_ENV_FILE = BIMOS_BASE / ".env"

if not BIMOS_ENV_FILE.exists():
    BIMOS_BASE.mkdir(parents=True, exist_ok=True)
    
    default_env = f"""# BIMOS Environment Configuration
# Please edit these paths and settings to match your setup.

# Server
BIMOS_HOST=127.0.0.1
BIMOS_PORT=8000
BIMOS_DEBUG=false

# Container Image
BIMOS_IMAGE=localhost/bimos/global:latest
BIMOS_USE_GPU=true

# Database
BIMOS_DATABASE_URL=postgresql://bimos:bimos@localhost/bimos

# Data Paths
BIMOS_WORKSPACE={(BIMOS_BASE / "workspace").as_posix()}
BIMOS_CACHE={(BIMOS_BASE / "cache").as_posix()}
BIMOS_LOGS={(BIMOS_BASE / "logs").as_posix()}
BIMOS_ESM_CACHE={(BIMOS_BASE / "cache" / "esm").as_posix()}

# QM Tools (Host Binaries)
# Provide the absolute path to the executable if installed.
ORCA_PATH=
GAUSSIAN_PATH=
"""
    BIMOS_ENV_FILE.write_text(default_env)
    print("============================================================", file=sys.stderr)
    print(" Welcome to BIMOS! A default configuration has been created:", file=sys.stderr)
    print(f"   {BIMOS_ENV_FILE}", file=sys.stderr)
    print(" Please edit this file to configure your workspace and paths,", file=sys.stderr)
    print(" then launch the software again.", file=sys.stderr)
    print("============================================================", file=sys.stderr)
    sys.exit(0)

load_dotenv(BIMOS_ENV_FILE)


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
    workspace_path: Path = Path(os.getenv("BIMOS_WORKSPACE", str(BIMOS_BASE / "workspace"))).expanduser().resolve()
    cache_path: Path = Path(os.getenv("BIMOS_CACHE", str(BIMOS_BASE / "cache"))).expanduser().resolve()
    logs_path: Path = Path(os.getenv("BIMOS_LOGS", str(BIMOS_BASE / "logs"))).expanduser().resolve()

    # ESM model cache
    esm_cache_path: Path = Path(os.getenv("BIMOS_ESM_CACHE", str(BIMOS_BASE / "cache" / "esm"))).expanduser().resolve()
    esm_model_url: str = "https://colabfold.steineggerlab.workers.dev/esm/esmfold.model"

    # Container image
    bimos_image: str = os.getenv("BIMOS_IMAGE", "localhost/bimos/global:latest")
    use_gpu: bool = os.getenv("BIMOS_USE_GPU", "true").lower() == "true"
    max_threads: bool = False

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
        "BIMOS_DATABASE_URL", "postgresql://bimos:bimos@localhost/bimos"
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
        """Create all required directories on first run."""
        for p in [
            self.base_path,
            self.workspace_path,
            self.cache_path,
            self.logs_path,
            self.esm_cache_path,
        ]:
            Path(p).mkdir(parents=True, exist_ok=True)


settings = Settings()
