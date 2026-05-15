"""
System and health endpoints.
"""

import psutil
import subprocess
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from bimos.infrastructure.database import search_ligands

router = APIRouter(tags=["System"])

@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/system/stats")
async def system_stats():
    """Get CPU, Memory and GPU statistics."""
    stats = {
        "cpu": psutil.cpu_percent(interval=None),
        "memory": psutil.virtual_memory().percent,
        "gpu": None
    }
    try:
        res = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8"
        )
        if res:
            parts = res.strip().split("\n")[0].split(",")
            stats["gpu"] = {
                "utilization": float(parts[0]),
                "memory_used": float(parts[1]),
                "memory_total": float(parts[2]),
                "memory_percent": (float(parts[1]) / float(parts[2])) * 100
            }
    except Exception:
        pass
    return stats

@router.get("/ligands")
async def list_ligands(
    q: str = Query("", description="Search term."),
    source: Optional[str] = Query(None, description="Filter by source."),
    limit: int = Query(50, le=500),
):
    """Search the ligand database."""
    try:
        results = search_ligands(query=q, source=source, limit=limit)
        return {
            "count": len(results),
            "ligands": [
                {
                    "id": r.id, "name": r.name, "cid": r.cid, "smiles": r.smiles,
                    "logp": r.logp, "molar_mass": r.molar_mass, "source": r.source,
                }
                for r in results
            ],
        }
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {exc}")
