"""Biokinetic helper functions and process-rate calculations."""
from __future__ import annotations

import math
from typing import Any

from .aeration import aeration_energy_rate, n2o_stripping_rate_per_day
from .parameters import ModelConfig


EPS = 1e-9



def _non_negative(value: float) -> float:
    return max(value, 0.0)



def monod(substrate: float, k_half: float) -> float:
    s = _non_negative(substrate)
    return s / (k_half + s + EPS)



def low_oxygen_factor(do_value: float, k_oxygen: float) -> float:
    do_value = _non_negative(do_value)
    return k_oxygen / (k_oxygen + do_value + EPS)



def bell_shaped_factor(value: float, optimum: float, width: float) -> float:
    return math.exp(-((value - optimum) / max(width, EPS)) ** 2)



def theta_correction(theta: float, temperature_c: float, reference_c: float = 20.0) -> float:
    return theta ** (temperature_c - reference_c)



def compute_process_rates(state: dict[str, float], config: ModelConfig, kla_o2_per_day: float, target_do: float) -> dict[str, float]:
    """Compute all biological, physical, and control-relevant rates.

    Rates are concentration-based and expressed in mg/L/day unless noted otherwise.
    """
    kin = config.kinetics
    reactor = config.reactor
    aeration = config.aeration

    s_nh4 = _non_negative(state["S_NH4"])
    s_no2 = _non_negative(state["S_NO2"])
    s_no3 = _non_negative(state["S_NO3"])
    s_n2o = _non_negative(state["S_N2O"])
    s_cod = _non_negative(state["S_COD"])
    s_o2 = _non_negative(state["S_O2"])
    x_aob = _non_negative(state["X_AOB"])
    x_nob = _non_negative(state["X_NOB"])
    x_het = _non_negative(state["X_HET"])

    temp_nit = theta_correction(kin.theta_nitrification, reactor.temperature_c)
    temp_den = theta_correction(kin.theta_denitrification, reactor.temperature_c)
    temp_red = theta_correction(kin.theta_reduction, reactor.temperature_c)

    f_ph_nit = bell_shaped_factor(reactor.pH, optimum=7.9, width=1.2)
    f_ph_den = bell_shaped_factor(reactor.pH, optimum=7.2, width=1.4)
    f_ph_red = bell_shaped_factor(reactor.pH, optimum=7.5, width=1.1)

    f_nh4 = monod(s_nh4, kin.k_nh4_mgN_L)
    f_no2_nob = monod(s_no2, kin.k_no2_nob_mgN_L)
    f_no2_den = monod(s_no2, kin.k_no2_den_mgN_L)
    f_no3_den = monod(s_no3, kin.k_no3_den_mgN_L)
    f_cod = monod(s_cod, kin.k_cod_mgCOD_L)

    f_o2_aob = monod(s_o2, kin.k_o2_aob_mg_L)
    f_o2_nob = monod(s_o2, kin.k_o2_nob_mg_L)
    f_anoxic = low_oxygen_factor(s_o2, kin.k_o2_het_mg_L)
    f_low_do_nd = low_oxygen_factor(s_o2, kin.k_o2_nd_mg_L)
    f_high_do_hao = monod(s_o2, kin.k_do_hao_mg_L)
    f_nitrite_nd = monod(s_no2, kin.k_no2_nd_mgN_L)
    f_n2o = monod(s_n2o, kin.k_n2o_mgN_L)
    f_cod_n2o_red = monod(s_cod, kin.k_cod_n2o_red_mgCOD_L)
    f_incomplete_den = kin.k_cod_incomplete_mgCOD_L / (kin.k_cod_incomplete_mgCOD_L + s_cod + EPS)

    r_aob = kin.q_aob_max_per_day * x_aob * f_nh4 * f_o2_aob * f_ph_nit * temp_nit
    r_nob = kin.q_nob_max_per_day * x_nob * f_no2_nob * f_o2_nob * f_ph_nit * temp_nit

    r_den_no2 = kin.q_den_max_per_day * x_het * f_no2_den * f_cod * f_anoxic * f_ph_den * temp_den
    r_den_no3 = 0.60 * kin.q_den_max_per_day * x_het * f_no3_den * f_cod * f_anoxic * f_ph_den * temp_den

    r_n2o_nd = kin.nd_yield * r_aob * f_low_do_nd * f_nitrite_nd
    r_n2o_hao = kin.hao_yield * r_aob * f_high_do_hao

    n2o_fraction_den = kin.den_n2o_yield_base * (1.0 + 1.2 * f_incomplete_den + 0.5 * f_no2_den)
    n2o_fraction_den = max(0.0, min(0.35, n2o_fraction_den))
    r_n2o_den = n2o_fraction_den * (r_den_no2 + r_den_no3)

    r_n2o_red = kin.k_red_per_day * x_het * f_n2o * f_cod_n2o_red * f_anoxic * f_ph_red * temp_red
    r_strip = n2o_stripping_rate_per_day(s_n2o, kla_o2_per_day, aeration)

    oxygen_uptake = kin.oxygen_per_nh4 * r_aob + kin.oxygen_per_no2 * r_nob
    cod_consumption = kin.cod_per_den_n * (r_den_no2 + r_den_no3) + kin.cod_per_n2o_red * r_n2o_red

    growth_aob = kin.y_aob_mgCOD_per_mgN * r_aob
    growth_nob = kin.y_nob_mgCOD_per_mgN * r_nob
    growth_het = kin.y_het_mgCOD_per_mgN * (r_den_no2 + r_den_no3 + 0.25 * r_n2o_red)

    energy_rate = aeration_energy_rate(kla_o2_per_day, aeration)
    emission_rate_kgN_d = r_strip * config.reactor.volume_m3 / 1000.0

    return {
        "target_do": target_do,
        "kla_o2_per_day": kla_o2_per_day,
        "r_aob": r_aob,
        "r_nob": r_nob,
        "r_den_no2": r_den_no2,
        "r_den_no3": r_den_no3,
        "r_n2o_nd": r_n2o_nd,
        "r_n2o_hao": r_n2o_hao,
        "r_n2o_den": r_n2o_den,
        "r_n2o_red": r_n2o_red,
        "r_strip": r_strip,
        "oxygen_uptake": oxygen_uptake,
        "cod_consumption": cod_consumption,
        "growth_aob": growth_aob,
        "growth_nob": growth_nob,
        "growth_het": growth_het,
        "energy_rate": energy_rate,
        "n2o_emission_rate_kgN_d": emission_rate_kgN_d,
    }
