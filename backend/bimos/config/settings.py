"""Centralized configuration for BIMOS."""

import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Application
    app_name: str = "BIMOS"
    app_version: str = "0.1.0"
    debug: bool = os.getenv("BIMOS_DEBUG", "false").lower() == "true"

    # Server
    host: str = os.getenv("BIMOS_HOST", "127.0.0.1")
    port: int = int(os.getenv("BIMOS_PORT", "8000"))

    # Paths
    base_path: Path = Path.home() / ".bimos"
    workspace_path: Path = Path.home() / ".bimos" / "workspace"
    cache_path: Path = Path.home() / ".bimos" / "cache"
    logs_path: Path = Path.home() / ".bimos" / "logs"

    # ESM model cache
    esm_cache_path: Path = Path.home() / ".bimos" / "cache" / "esm"
    esm_model_url: str = "https://colabfold.steineggerlab.workers.dev/esm/esmfold.model"

    # Container image
    bimos_image: str = os.getenv("BIMOS_IMAGE", "bimos/global:latest")
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
    orca_path: str = os.getenv("ORCA_PATH", "")
    gaussian_path: str = os.getenv("GAUSSIAN_PATH", "")

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
