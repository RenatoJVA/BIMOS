"""
System and health endpoints.
"""

import asyncio
import subprocess

from fastapi import APIRouter

router = APIRouter(tags=["System"])


@router.get("/health")
async def health():  # type: ignore[no-untyped-def]
    return {"status": "ok"}


def _gather_stats() -> dict[str, object]:
    """Collect CPU, memory and GPU stats (blocking; run off the event loop)."""
    import psutil

    stats: dict[str, object] = {
        "cpu": psutil.cpu_percent(interval=None),
        "memory": psutil.virtual_memory().percent,
        "gpu": None,
    }
    try:
        res = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            encoding="utf-8",
        )
        if res:
            parts = res.strip().split("\n")[0].split(",")
            memory_total = float(parts[2])
            stats["gpu"] = {
                "utilization": float(parts[0]),
                "memory_used": float(parts[1]),
                "memory_total": memory_total,
                "memory_percent": (float(parts[1]) / memory_total) * 100 if memory_total else 0.0,
            }
    except Exception:
        pass
    return stats


@router.get("/system/stats")
async def system_stats():  # type: ignore[no-untyped-def]
    """Get CPU, Memory and GPU statistics."""
    # nvidia-smi and psutil are blocking, so run them in a worker thread to
    # avoid stalling the event loop.
    return await asyncio.to_thread(_gather_stats)
