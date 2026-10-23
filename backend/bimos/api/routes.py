"""
BIMOS FastAPI router configuration.
Modularized by domain to improve maintainability.
"""

from fastapi import APIRouter, Depends

from bimos.api.endpoints import config, dock, jobs, ligands, predict, simulate, system, tokens
from bimos.api.security import require_api_token

router = APIRouter(prefix="/api/v1")

# Health stays public (container probes); every data/job endpoint is protected
# when BIMOS_API_TOKEN is configured.
router.include_router(system.router)

protected = APIRouter(dependencies=[Depends(require_api_token)])
protected.include_router(config.router)
protected.include_router(jobs.router)
protected.include_router(predict.router)
protected.include_router(dock.router)
protected.include_router(simulate.router)
protected.include_router(ligands.router)
protected.include_router(tokens.router)
router.include_router(protected)
