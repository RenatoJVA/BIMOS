"""Docking configuration resolved from user YAML profiles."""

from __future__ import annotations

import math
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
            grid = {**grid, **{k: v for k, v in overrides.items() if k in {
                "mode", "center_x", "center_y", "center_z", "size_x", "size_y", "size_z"
            }}}

        cpu = vina.get("cpu_per_job", settings.get_threads())
        mode = str(grid.get("mode", "auto")).lower()
        if mode not in ("auto", "manual"):
            raise ValueError(f"Invalid grid.mode '{mode}': use 'auto' or 'manual'.")
        center = (
            _optional_float(grid.get("center_x")),
            _optional_float(grid.get("center_y")),
            _optional_float(grid.get("center_z")),
        )
        size = (
            _optional_float(grid.get("size_x")),
            _optional_float(grid.get("size_y")),
            _optional_float(grid.get("size_z")),
        )
        if mode == "manual":
            if any(v is None for v in (*center, *size)):
                raise ValueError(
                    "grid.mode 'manual' requires center_x/y/z + size_x/y/z "
                    "(docking.yaml or --center/--size flags)."
                )
            size = tuple(_check_size(v, name) for v, name in zip(size, ("size_x", "size_y", "size_z"), strict=True))  # type: ignore[assignment]
        return cls(
            times=int(clamp(int(vina.get("times", 10)), 1, 100)),
            margin=float(clamp(float(vina.get("margin", 1.0)), 0.1, 20.0)),
            num_modes=int(clamp(int(vina.get("num_modes", 20)), 1, 100)),
            exhaustiveness=int(clamp(int(vina.get("exhaustiveness", 12)), 1, 32)),
            energy_range=float(clamp(float(vina.get("energy_range", 3.0)), 1.0, 20.0)),
            cpu_per_job=int(clamp(int(cpu), 1, settings.get_threads() if settings.max_threads else 64)),
            grid_mode=mode,
            center_x=center[0],
            center_y=center[1],
            center_z=center[2],
            size_x=size[0],
            size_y=size[1],
            size_z=size[2],
            profile=profile.value,
        )


_MAX_BOX_SIZE = 100.0


def _optional_float(value: Any) -> float | None:
    if value is None or value == "null":
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"Invalid numeric value for grid: {value!r}.") from None
    if math.isnan(result) or math.isinf(result):
        raise ValueError(f"Invalid numeric value for grid: {value!r}.")
    return result


def _check_size(value: float | None, name: str) -> float:
    if value is None or value <= 0:
        raise ValueError(f"{name} must be > 0 (got {value}).")
    if value > _MAX_BOX_SIZE:
        raise ValueError(f"{name}={value} exceeds the maximum {_MAX_BOX_SIZE:g} A.")
    return value
