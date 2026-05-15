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
    
    default_env = f"""# ==============================================================================
#                     BIMOS ENVIRONMENT CONFIGURATION
# ==============================================================================
# This file controls the global settings for the Biomolecular Modeling Suite.
# Changes here will be applied the next time you run `bimos` or the GUI.

# ------------------------------------------------------------------------------
# 1. CORE SERVER SETTINGS
# ------------------------------------------------------------------------------
# The address and port where the local API server will run.
BIMOS_HOST=127.0.0.1
BIMOS_PORT=8000
BIMOS_DEBUG=false

# ------------------------------------------------------------------------------
# 2. COMPUTATIONAL ENGINE (PODMAN / DOCKER)
# ------------------------------------------------------------------------------
# The container image containing GROMACS, AutoDock Vina, RDKit, Meeko, etc.
# By default it uses the local image. You can specify a Docker Hub image if needed.
BIMOS_IMAGE=localhost/bimos/global:latest

# Enable/Disable GPU acceleration (CUDA/OpenCL) for MD and ESMFold.
BIMOS_USE_GPU=true

# ------------------------------------------------------------------------------
# 3. DIRECTORY PATHS
# ------------------------------------------------------------------------------
# BIMOS_WORKSPACE: Where all docking, MD, and prediction jobs are executed.
# BIMOS_CACHE: Where temporary files and downloaded models are stored.
BIMOS_WORKSPACE={(BIMOS_BASE / "workspace").as_posix()}
BIMOS_CACHE={(BIMOS_BASE / "cache").as_posix()}
BIMOS_LOGS={(BIMOS_BASE / "logs").as_posix()}
BIMOS_ESM_CACHE={(BIMOS_BASE / "cache" / "esm").as_posix()}

# ------------------------------------------------------------------------------
# 4. DATABASE INTEGRATION
# ------------------------------------------------------------------------------
# Connection string for the PostgreSQL database (if used for tracking workflows).
# Local SQLite curated datasets (ChEMBL) are managed automatically.
BIMOS_DATABASE_URL=postgresql://bimos:bimos@localhost/bimos

# ------------------------------------------------------------------------------
# 5. QUANTUM MECHANICS (HOST BINARIES)
# ------------------------------------------------------------------------------
# BIMOS runs QM software directly on the host (not inside the container).
# Provide the absolute path to your local ORCA or Gaussian 16 executables.
# Example: ORCA_PATH=/opt/orca/orca
ORCA_PATH=
GAUSSIAN_PATH=

# ------------------------------------------------------------------------------
# 6. DISTRIBUTED EXECUTION (THIN CLIENT)
# ------------------------------------------------------------------------------
# BIMOS_REMOTE_URL: If set, the Desktop UI will connect to this remote API 
#                   instead of starting a local server (e.g. http://10.0.0.5:8000).
# BIMOS_SSH_HOST: If set, the local BIMOS engine will dispatch container tasks
#                 via SSH to the target machine (e.g. 10.0.0.5).
# BIMOS_REMOTE_URL=
# BIMOS_SSH_HOST=
# BIMOS_SSH_USER=
# BIMOS_SSH_KEY=
# ==============================================================================
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

    # Remote Connection
    remote_url: str = os.getenv("BIMOS_REMOTE_URL", "")  # e.g., http://192.168.1.100:8000
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
