"""
User configuration endpoints.
"""

from fastapi import APIRouter, Query

from bimos.config.settings import settings
from bimos.shared.user_config import ensure_user_configs, is_custom, resolve, user_config_dir

router = APIRouter(prefix="/config", tags=["Configuration"])

_PROCESS_NAMES = ("docking", "md", "esmfold", "boltz", "orca", "gaussian")


@router.get("/profiles")
async def list_config_profiles(preview_max: bool = Query(False)):
    """Return config file paths and active profile per process."""
    settings.ensure_dirs()
    ensure_user_configs()
    processes = {}
    for name in _PROCESS_NAMES:
        _, profile = resolve(name, max_mode=preview_max)
        processes[name] = {
            "profile": profile.value,
            "custom": is_custom(name),
            "path": str(user_config_dir() / f"{name}.yaml"),
        }
    return {"config_dir": str(user_config_dir()), "processes": processes}
