"""
User configuration endpoints.
"""

from fastapi import APIRouter, Query

from bimos.config.settings import settings
from bimos.shared.paths import PROCESS_CONFIG_FILES
from bimos.shared.user_config import ensure_user_configs, is_custom, resolve, user_config_dir

router = APIRouter(prefix="/config", tags=["Configuration"])


@router.get("/profiles")
async def list_config_profiles(preview_max: bool = Query(False)):  # type: ignore[no-untyped-def]
    """Return config file paths and active profile per process."""
    settings.ensure_dirs()
    ensure_user_configs()
    processes = {}
    for name in PROCESS_CONFIG_FILES:
        _, profile = resolve(name, max_mode=preview_max)
        processes[name] = {
            "profile": profile.value,
            "custom": is_custom(name),
            "path": str(user_config_dir() / f"{name}.yaml"),
        }
    return {"config_dir": str(user_config_dir()), "processes": processes}
