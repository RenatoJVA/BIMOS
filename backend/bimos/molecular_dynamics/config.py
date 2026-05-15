"""MD configuration resolved from user YAML profiles."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from bimos.shared.user_config import clamp, resolve


@dataclass(frozen=True)
class MDConfig:
    sdm_steps_holo: int
    sdm_steps_apo: int
    nvt_npt_steps: int
    ion_concentration: str
    box_distance: str
    max_min_iterations: int
    forcefield: str
    water_model: str
    solvent_gro: str
    profile: str

    @classmethod
    def resolve(cls, *, max_mode: bool | None = None) -> MDConfig:
        data, profile = resolve("md", max_mode=max_mode)
        sim = data.get("simulation", {})
        prep = data.get("prep", {})
        return cls(
            sdm_steps_holo=int(clamp(int(sim.get("sdm_steps_holo", 50_000_000)), 1_000, 500_000_000)),
            sdm_steps_apo=int(clamp(int(sim.get("sdm_steps_apo", 250_000_000)), 1_000, 1_000_000_000)),
            nvt_npt_steps=int(clamp(int(sim.get("nvt_npt_steps", 5000)), 100, 10_000_000)),
            ion_concentration=str(sim.get("ion_concentration", "0.154004106")),
            box_distance=str(sim.get("box_distance", "1.0")),
            max_min_iterations=int(clamp(int(sim.get("max_min_iterations", 15)), 1, 100)),
            forcefield=str(prep.get("forcefield", "oplsaa")),
            water_model=str(prep.get("water_model", "tip3p")),
            solvent_gro=str(prep.get("solvent_gro", "spc216.gro")),
            profile=profile.value,
        )
