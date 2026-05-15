"""Docking configuration resolved from user YAML profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bimos.config.settings import settings
from bimos.shared.user_config import clamp, resolve


@dataclass(frozen=True)
class DockingConfig:
    times: int
    margin: float
    num_modes: int
    exhaustiveness: int
    energy_range: float
    cpu_per_job: int
    grid_mode: str
    center_x: float | None
    center_y: float | None
    center_z: float | None
    size_x: float | None
    size_y: float | None
    size_z: float | None
    profile: str

    @classmethod
    def resolve(cls, *, max_mode: bool | None = None, **overrides: Any) -> DockingConfig:
        data, profile = resolve("docking", max_mode=max_mode)
        vina = data.get("vina", {})
        grid = data.get("grid", {})

        if overrides:
            vina = {**vina, **{k: v for k, v in overrides.items() if k in {
                "times", "margin", "num_modes", "exhaustiveness", "energy_range", "cpu_per_job"
            }}}

        cpu = vina.get("cpu_per_job", settings.get_threads())
        return cls(
            times=int(clamp(int(vina.get("times", 10)), 1, 100)),
            margin=float(clamp(float(vina.get("margin", 1.0)), 0.1, 20.0)),
            num_modes=int(clamp(int(vina.get("num_modes", 20)), 1, 100)),
            exhaustiveness=int(clamp(int(vina.get("exhaustiveness", 12)), 1, 32)),
            energy_range=float(clamp(float(vina.get("energy_range", 3.0)), 1.0, 20.0)),
            cpu_per_job=int(clamp(int(cpu), 1, settings.get_threads() if settings.max_threads else 64)),
            grid_mode=str(grid.get("mode", "auto")).lower(),
            center_x=_optional_float(grid.get("center_x")),
            center_y=_optional_float(grid.get("center_y")),
            center_z=_optional_float(grid.get("center_z")),
            size_x=_optional_float(grid.get("size_x")),
            size_y=_optional_float(grid.get("size_y")),
            size_z=_optional_float(grid.get("size_z")),
            profile=profile.value,
        )


def _optional_float(value: Any) -> float | None:
    if value is None or value == "null":
        return None
    return float(value)
