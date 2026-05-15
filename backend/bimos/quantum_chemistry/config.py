"""QM configuration resolved from user YAML profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from bimos.config.settings import settings
from bimos.shared.user_config import clamp, resolve


def _default_nprocs() -> int:
    return settings.get_threads()


@dataclass(frozen=True)
class OrcaConfig:
    method: str
    basis: str
    maxcore_mb: int
    max_iter: int
    max_jobs: int
    charge: int
    nprocs: int = field(default_factory=_default_nprocs)
    profile: str = "default"

    @classmethod
    def resolve(cls, *, max_mode: bool | None = None, charge: int | None = None) -> OrcaConfig:
        data, profile = resolve("orca", max_mode=max_mode)
        block = data.get("orca", {})
        job = data.get("job", {})
        return cls(
            method=str(block.get("method", "CAM-B3LYP")),
            basis=str(block.get("basis", "def2-TZVP")),
            maxcore_mb=int(clamp(int(block.get("maxcore_mb", 32000)), 512, 128000)),
            max_iter=int(clamp(int(block.get("max_iter", 512)), 50, 2000)),
            max_jobs=int(clamp(int(block.get("max_jobs", 2)), 1, 32)),
            charge=int(charge if charge is not None else job.get("charge", 0)),
            profile=profile.value,
        )


@dataclass(frozen=True)
class GaussianConfig:
    route: str
    mem: str
    max_jobs: int
    charge: int
    nprocs: int = field(default_factory=_default_nprocs)
    profile: str = "default"

    @classmethod
    def resolve(cls, *, max_mode: bool | None = None, charge: int | None = None) -> GaussianConfig:
        data, profile = resolve("gaussian", max_mode=max_mode)
        block = data.get("gaussian", {})
        job = data.get("job", {})
        return cls(
            route=str(block.get("route", "cam-b3lyp tzvp pop=hirshfeld scf=(xqc,maxcycle=512)")),
            mem=str(block.get("mem", "32GB")),
            max_jobs=int(clamp(int(block.get("max_jobs", 2)), 1, 32)),
            charge=int(charge if charge is not None else job.get("charge", 0)),
            profile=profile.value,
        )
