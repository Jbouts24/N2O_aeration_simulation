"""ODE system for the equivalent secondary-treatment reactor."""
from __future__ import annotations

import numpy as np

from .aeration import oxygen_kla_per_day
from .controller import BaseDOController
from .kinetics import compute_process_rates
from .parameters import ModelConfig
from .states import StateIndex, state_to_dict


class SecondaryTreatmentModel:
    """Single mixed-reactor N2O model with retained biomass and DO control."""

    def __init__(self, config: ModelConfig, controller: BaseDOController) -> None:
        self.config = config
        self.controller = controller
        self.q_over_v_per_day = 1.0 / config.reactor.hrt_days
        self.srt_loss_per_day = 1.0 / config.reactor.srt_days

    def _controller_outputs(self, t_days: float, y: np.ndarray) -> tuple[float, float, dict[str, float]]:
        state = state_to_dict(y)
        target_do = self.controller.target_do(t_days, state)
        kla_o2 = oxygen_kla_per_day(state["S_O2"], target_do, self.config.controller)
        rates = compute_process_rates(state, self.config, kla_o2, target_do)
        return target_do, kla_o2, rates

    def rhs(self, t_days: float, y: np.ndarray) -> np.ndarray:
        cfg = self.config
        infl = cfg.influent
        kin = cfg.kinetics

        _, _, rates = self._controller_outputs(t_days, y)

        s_nh4 = max(float(y[StateIndex.S_NH4]), 0.0)
        s_no2 = max(float(y[StateIndex.S_NO2]), 0.0)
        s_no3 = max(float(y[StateIndex.S_NO3]), 0.0)
        s_n2o = max(float(y[StateIndex.S_N2O]), 0.0)
        s_cod = max(float(y[StateIndex.S_COD]), 0.0)
        s_o2 = max(float(y[StateIndex.S_O2]), 0.0)
        x_aob = max(float(y[StateIndex.X_AOB]), 0.0)
        x_nob = max(float(y[StateIndex.X_NOB]), 0.0)
        x_het = max(float(y[StateIndex.X_HET]), 0.0)

        dy = np.zeros_like(y)

        dy[StateIndex.S_NH4] = self.q_over_v_per_day * (infl.nh4_mgN_L - s_nh4) - rates["r_aob"]
        dy[StateIndex.S_NO2] = self.q_over_v_per_day * (infl.no2_mgN_L - s_no2) + rates["r_aob"] - rates["r_nob"] - rates["r_den_no2"]
        dy[StateIndex.S_NO3] = self.q_over_v_per_day * (infl.no3_mgN_L - s_no3) + rates["r_nob"] - rates["r_den_no3"]
        dy[StateIndex.S_N2O] = (
            self.q_over_v_per_day * (0.0 - s_n2o)
            + rates["r_n2o_nd"]
            + rates["r_n2o_hao"]
            + rates["r_n2o_den"]
            - rates["r_n2o_red"]
            - rates["r_strip"]
        )
        dy[StateIndex.S_COD] = self.q_over_v_per_day * (infl.cod_mgCOD_L - s_cod) - rates["cod_consumption"]
        dy[StateIndex.S_O2] = (
            self.q_over_v_per_day * (infl.do_mgO2_L - s_o2)
            + rates["kla_o2_per_day"] * (cfg.aeration.do_sat_mg_L - s_o2)
            - rates["oxygen_uptake"]
        )

        dy[StateIndex.X_AOB] = rates["growth_aob"] - kin.b_aob_per_day * x_aob - self.srt_loss_per_day * x_aob
        dy[StateIndex.X_NOB] = rates["growth_nob"] - kin.b_nob_per_day * x_nob - self.srt_loss_per_day * x_nob
        dy[StateIndex.X_HET] = rates["growth_het"] - kin.b_het_per_day * x_het - self.srt_loss_per_day * x_het

        return dy

    def diagnostics(self, t_days: float, y: np.ndarray) -> dict[str, float]:
        _, _, rates = self._controller_outputs(t_days, y)
        return rates
