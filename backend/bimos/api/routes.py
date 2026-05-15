"""
BIMOS FastAPI router configuration.
Modularized by domain to improve maintainability.
"""

from fastapi import APIRouter
from bimos.api.endpoints import config, jobs, predict, dock, simulate, system

router = APIRouter(prefix="/api/v1")

# Include sub-routers
router.include_router(system.router)
router.include_router(config.router)
router.include_router(jobs.router)
router.include_router(predict.router)
router.include_router(dock.router)
router.include_router(simulate.router)
