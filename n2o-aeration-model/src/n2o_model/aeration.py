"""Aeration and gas-transfer helper functions."""
from __future__ import annotations

from .parameters import AerationSettings, ControllerSettings



def oxygen_kla_per_day(current_do: float, target_do: float, controller: ControllerSettings) -> float:
    """Simple proportional aeration law that maps DO error to oxygen transfer.

    This is intentionally simple in v1. The DO controller is represented as a direct
    proportional conversion from setpoint error to oxygen transfer coefficient.
    """
    error = max(target_do - current_do, 0.0)
    kla = controller.min_kla_per_day + controller.kp * error
    return max(controller.min_kla_per_day, min(controller.max_kla_per_day, kla))



def n2o_stripping_rate_per_day(s_n2o: float, kla_o2: float, aeration: AerationSettings) -> float:
    """Lumped stripping model for dissolved N2O during aeration."""
    return aeration.n2o_kla_factor * kla_o2 * max(s_n2o, 0.0)



def aeration_energy_rate(kla_o2: float, aeration: AerationSettings) -> float:
    """Aeration energy proxy. Units are arbitrary but consistent within the repo."""
    return aeration.energy_per_kla * kla_o2
