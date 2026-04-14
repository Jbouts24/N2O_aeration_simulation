"""State ordering and helpers for state vectors."""
from __future__ import annotations

from enum import IntEnum

import numpy as np

from .parameters import ModelConfig


class StateIndex(IntEnum):
    S_NH4 = 0
    S_NO2 = 1
    S_NO3 = 2
    S_N2O = 3
    S_COD = 4
    S_O2 = 5
    X_AOB = 6
    X_NOB = 7
    X_HET = 8


STATE_NAMES = [member.name for member in StateIndex]



def initial_state_vector(config: ModelConfig) -> np.ndarray:
    """Build the initial state vector from the configuration."""
    ic = config.initial_conditions
    bio = config.biomass_initial
    return np.array(
        [
            ic.nh4_mgN_L,
            ic.no2_mgN_L,
            ic.no3_mgN_L,
            ic.n2o_mgN_L,
            ic.cod_mgCOD_L,
            ic.do_mgO2_L,
            bio.aob_mgCOD_L,
            bio.nob_mgCOD_L,
            bio.het_mgCOD_L,
        ],
        dtype=float,
    )



def state_to_dict(y: np.ndarray) -> dict[str, float]:
    return {name: float(y[idx]) for idx, name in enumerate(STATE_NAMES)}
