"""
User-facing YAML configuration per computational process.

Profiles:
  - default: packaged defaults (~/.bimos/config/*.yaml unchanged)
  - custom:  user edited their YAML (differs from packaged default)
  - max:     CLI ``--max`` overlays resource-intensive values on the active profile
"""

from __future__ import annotations

import json
import shutil
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from bimos.config.settings import settings
from bimos.shared.paths import DEFAULTS_DIR

PROCESS_CONFIG_FILES = (
    "docking",
    "md",
    "esmfold",
    "boltz",
    "orca",
    "gaussian",
)


class ConfigProfile(StrEnum):
    DEFAULT = "default"
    CUSTOM = "custom"
    MAX = "max"


def user_config_dir() -> Path:
    return settings.base_path / "config"


def _packaged_path(name: str) -> Path:
    return DEFAULTS_DIR / f"{name}.yaml"


def _packaged_default_yaml(name: str) -> dict[str, Any]:
    path = _packaged_path(name)
    if path.exists():
        return _load_yaml(path)
    resource = resources.files("bimos.config.defaults").joinpath(f"{name}.yaml")
    return yaml.safe_load(resource.read_text(encoding="utf-8")) or {}


def _user_path(name: str) -> Path:
    return user_config_dir() / f"{name}.yaml"


def _canonical(data: Any) -> str:
    return json.dumps(data, sort_keys=True, default=str)


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def is_custom(name: str) -> bool:
    """True when the user YAML differs from the packaged default."""
    user = _user_path(name)
    if not user.exists():
        return False
    packaged = _packaged_default_yaml(name)
    if not packaged:
        return False
    return _canonical(_load_yaml(user)) != _canonical(packaged)


def ensure_user_configs() -> None:
    """Create ``~/.bimos/config/*.yaml`` from packaged defaults on first run."""
    directory = user_config_dir()
    directory.mkdir(parents=True, exist_ok=True)
    for name in PROCESS_CONFIG_FILES:
        packaged = _packaged_path(name)
        user = _user_path(name)
        if not user.exists():
            if packaged.exists():
                shutil.copy2(packaged, user)
            else:
                resource = resources.files("bimos.config.defaults").joinpath(
                    f"{name}.yaml"
                )
                user.write_text(resource.read_text(encoding="utf-8"), encoding="utf-8")


def _max_patch(name: str, data: dict[str, Any]) -> dict[str, Any]:
    """Apply resource-max overrides without touching non-resource tunables."""
    threads = settings.get_threads()
    patched = yaml.safe_load(yaml.safe_dump(data)) or {}

    if name == "docking":
        vina = patched.setdefault("vina", {})
        vina["cpu_per_job"] = threads
        vina["times"] = max(int(vina.get("times", 10)), 20)
        vina["exhaustiveness"] = max(int(vina.get("exhaustiveness", 12)), 16)
    elif name == "boltz":
        patched["num_workers"] = threads
        patched["preprocessing_threads"] = threads
        patched["max_parallel_samples"] = min(threads, 12)
    elif name in ("orca", "gaussian"):
        key = "orca" if name == "orca" else "gaussian"
        block = patched.setdefault(key, {})
        if name == "orca":
            block["maxcore_mb"] = 64000
        else:
            block["mem"] = "64GB"
        block["max_jobs"] = max(int(block.get("max_jobs", 2)), threads // 2 or 1)

    return patched


def resolve(
    name: str,
    *,
    max_mode: bool | None = None,
    overrides: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], ConfigProfile]:
    """
    Resolve configuration for *name*.

    Returns merged data and the effective profile label.
    """
    ensure_user_configs()
    packaged = _packaged_default_yaml(name)
    user = _load_yaml(_user_path(name))

    if is_custom(name):
        data = user
        profile = ConfigProfile.CUSTOM
    else:
        data = yaml.safe_load(yaml.safe_dump(packaged)) or {}
        profile = ConfigProfile.DEFAULT

    use_max = max_mode if max_mode is not None else settings.max_threads
    if use_max:
        data = _max_patch(name, data)
        profile = ConfigProfile.MAX

    if overrides:
        data = _deep_merge(data, overrides)

    return data, profile


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    result = yaml.safe_load(yaml.safe_dump(base)) or {}
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def clamp(value: int | float, low: int | float, high: int | float) -> int | float:
    return max(low, min(high, value))
