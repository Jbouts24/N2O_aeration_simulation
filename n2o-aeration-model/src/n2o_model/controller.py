"""DO control strategies used by the simulator."""
from __future__ import annotations

from abc import ABC, abstractmethod

from .parameters import ControllerSettings


class BaseDOController(ABC):
    def __init__(self, settings: ControllerSettings) -> None:
        self.settings = settings

    @abstractmethod
    def target_do(self, t_days: float, state: dict[str, float]) -> float:
        """Return the controller's target DO in mg/L."""


class FixedDOController(BaseDOController):
    def target_do(self, t_days: float, state: dict[str, float]) -> float:
        return self.settings.target_do_mg_L


class DemandDOController(BaseDOController):
    def target_do(self, t_days: float, state: dict[str, float]) -> float:
        nh4 = max(state["S_NH4"], 0.0)
        low = self.settings.nh4_low_mgN_L
        high = self.settings.nh4_high_mgN_L
        do_low = self.settings.target_do_low_mg_L
        do_mid = self.settings.target_do_mid_mg_L
        do_high = self.settings.target_do_high_mg_L

        if nh4 <= low:
            return do_low
        if nh4 >= high:
            return do_high

        midpoint = 0.5 * (low + high)
        if nh4 <= midpoint:
            frac = (nh4 - low) / max(midpoint - low, 1e-9)
            return do_low + frac * (do_mid - do_low)

        frac = (nh4 - midpoint) / max(high - midpoint, 1e-9)
        return do_mid + frac * (do_high - do_mid)



def build_controller(settings: ControllerSettings) -> BaseDOController:
    controller_type = settings.type.strip().lower()
    if controller_type == "fixed":
        return FixedDOController(settings)
    if controller_type in {"demand", "dynamic", "rule_based"}:
        return DemandDOController(settings)
    raise ValueError(f"Unknown controller type: {settings.type}")
