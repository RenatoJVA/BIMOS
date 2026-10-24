"""Centralized configuration for BIMOS."""

import json
import os
import shutil
import sys
from importlib import resources
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from dotenv import load_dotenv

from bimos.shared.paths import DEFAULTS_DIR, PROCESS_CONFIG_FILES

BIMOS_BASE = (
    Path(os.getenv("BIMOS_BASE_PATH", Path.home() / ".bimos")).expanduser().resolve()
)
BIMOS_ENV_FILE = BIMOS_BASE / ".env"


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


def _bootstrap_first_run(*, announce: bool = True) -> None:
    """Create .env and config files on first run.

    This is called only from :func:`initialize`, never at import time.
    """
    BIMOS_BASE.mkdir(parents=True, exist_ok=True)
    BIMOS_ENV_FILE.write_text(_render_env_template(), encoding="utf-8")
    _bootstrap_user_configs()
    if not announce:
        return
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


def _package_version() -> str:
    """Version declared once in ``pyproject.toml`` and installed as metadata."""
    try:
        return version("bimos")
    except PackageNotFoundError:
        return "0.0.0+unknown"


class Settings:
    def __init__(self) -> None:
        self.reload()

    def reload(self) -> None:
        """Read environment variables into this instance.

        Importing this module is side-effect free: the process environment is
        snapshotted here, but the user ``.env`` is loaded only by
        :func:`initialize` (CLI/API startup).
        """
        # Application
        self.app_name = "BIMOS"
        self.app_version = _package_version()
        self.debug = os.getenv("BIMOS_DEBUG", "false").lower() == "true"

        # Server
        self.host = os.getenv("BIMOS_HOST", "127.0.0.1")
        self.port = int(os.getenv("BIMOS_PORT", "8000"))
        # ``local`` runs jobs on this host; ``disabled`` serves the UI/API without
        # executing pipelines (the supported mode for the reference compose stack).
        self.execution_mode = os.getenv("BIMOS_EXECUTION_MODE", "local").strip().lower()
        # Required whenever the API is bound outside loopback. Empty means the
        # default local-only deployment, which does not need a token.
        self.api_token = os.getenv("BIMOS_API_TOKEN", "")
        # Optional native TLS. Both files must be configured together.
        self.tls_certfile = os.getenv("BIMOS_TLS_CERTFILE", "").strip()
        self.tls_keyfile = os.getenv("BIMOS_TLS_KEYFILE", "").strip()

        # Paths
        self.base_path = BIMOS_BASE
        self.workspace_path = (
            Path(os.getenv("BIMOS_WORKSPACE", str(BIMOS_BASE / "workspace")))
            .expanduser()
            .resolve()
        )
        self.cache_path = (
            Path(os.getenv("BIMOS_CACHE", str(BIMOS_BASE / "cache"))).expanduser().resolve()
        )
        self.logs_path = (
            Path(os.getenv("BIMOS_LOGS", str(BIMOS_BASE / "logs"))).expanduser().resolve()
        )

        # Container image
        self.bimos_image = os.getenv("BIMOS_IMAGE", "localhost/bimos/global:latest")
        self.use_gpu = os.getenv("BIMOS_USE_GPU", "true").lower() == "true"
        self.max_threads = False

        # Remote Connection
        self.remote_url = os.getenv("BIMOS_REMOTE_URL", "")  # e.g., http://192.168.1.100:8000
        self.ssh_host = os.getenv("BIMOS_SSH_HOST", "")
        self.ssh_user = os.getenv("BIMOS_SSH_USER", "")
        self.ssh_key = os.getenv("BIMOS_SSH_KEY", "")

        # Database
        self.database_url = os.getenv("BIMOS_DATABASE_URL", "")

    @staticmethod
    def _physical_core_count() -> int:
        """Count physical CPU cores (not hyperthreads)."""
        try:
            cores: set[str] = set()
            for cpu_path in Path("/sys/devices/system/cpu").glob("cpu[0-9]*"):
                core_file = cpu_path / "topology" / "core_id"
                if core_file.exists():
                    cores.add(core_file.read_text().strip())
            if cores:
                return len(cores)
        except OSError:
            pass
        return os.cpu_count() or 1

    def get_threads(self) -> int:
        """Calculate number of threads based on max_threads flag."""
        total = self._physical_core_count()
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

    def _write_paths_manifest(self) -> None:
        """Record the effective paths so the uninstaller can find custom ones.

        ``BIMOS_WORKSPACE``/``BIMOS_CACHE``/``BIMOS_LOGS`` may point outside
        ``~/.bimos``; without this file a purge could not discover them.
        Best effort: a read-only or missing home must never break the CLI.
        """
        target = self.base_path / "paths.json"
        payload = {
            "version": 1,
            "base": str(self.base_path),
            "workspace": str(self.workspace_path),
            "cache": str(self.cache_path),
            "logs": str(self.logs_path),
            "image": self.bimos_image,
            "app_version": self.app_version,
        }
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        try:
            if target.is_file() and target.read_text(encoding="utf-8") == text:
                return
            tmp = target.with_name("paths.json.tmp")
            tmp.write_text(text, encoding="utf-8")
            tmp.replace(target)
        except OSError:
            return

    def ensure_dirs(self) -> None:
        """Create all required directories and user config files on first run."""
        for p in [
            self.base_path,
            self.workspace_path,
            self.cache_path,
            self.logs_path,
        ]:
            Path(p).mkdir(parents=True, exist_ok=True)

        self._write_paths_manifest()

        from bimos.shared.user_config import ensure_user_configs

        ensure_user_configs()


settings = Settings()


def initialize(*, announce: bool = True) -> bool:
    """Load ``~/.bimos/.env``, creating the user config on first run.

    Returns ``True`` when the first-run bootstrap created files. Safe to call
    more than once; importers only get a snapshot of the process environment.
    """
    created = False
    if not BIMOS_ENV_FILE.exists():
        _bootstrap_first_run(announce=announce)
        created = True
    load_dotenv(BIMOS_ENV_FILE, override=False)
    settings.reload()
    return created
