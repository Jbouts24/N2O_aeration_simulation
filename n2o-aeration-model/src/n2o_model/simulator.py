"""Simulation runner and summary helpers.

This module intentionally keeps the baseline `run_simulation(config)` API stable while
also exposing a few optional arguments that make interactive / chunked simulation easy.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd
from scipy.integrate import cumulative_trapezoid, solve_ivp

from .controller import BaseDOController, build_controller
from .parameters import ModelConfig
from .process_model import SecondaryTreatmentModel
from .states import STATE_NAMES, initial_state_vector
from .utils import ensure_dir


@dataclass
class SimulationResults:
    config: ModelConfig
    dataframe: pd.DataFrame
    solver_message: str
    success: bool



def _build_dataframe(config: ModelConfig, model: SecondaryTreatmentModel, sol) -> pd.DataFrame:
    """Convert a SciPy solution object into the repo's standard results dataframe."""
    df = pd.DataFrame(sol.y.T, columns=STATE_NAMES)
    df.insert(0, "time_days", sol.t)
    df[STATE_NAMES] = df[STATE_NAMES].clip(lower=0.0)

    diagnostics = [
        model.diagnostics(t, row[STATE_NAMES].to_numpy(dtype=float))
        for t, (_, row) in zip(sol.t, df.iterrows())
    ]
    diag_df = pd.DataFrame(diagnostics)
    df = pd.concat([df, diag_df], axis=1)

    df["cum_n2o_emitted_kgN"] = cumulative_trapezoid(
        df["n2o_emission_rate_kgN_d"], df["time_days"], initial=0.0
    )
    df["cum_aeration_energy"] = cumulative_trapezoid(df["energy_rate"], df["time_days"], initial=0.0)
    df["scenario_name"] = config.scenario_name
    df["pH"] = config.reactor.pH
    df["temperature_c"] = config.reactor.temperature_c
    df["controller_type"] = config.controller.type
    return df



def run_simulation(
    config: ModelConfig,
    initial_state: Optional[np.ndarray] = None,
    duration_days: Optional[float] = None,
    time_offset_days: float = 0.0,
    controller_override: Optional[BaseDOController] = None,
) -> SimulationResults:
    """Run one deterministic simulation.

    Parameters
    ----------
    config:
        Full model configuration.
    initial_state:
        Optional state vector to start from. If omitted, the initial conditions in
        the configuration are used.
    duration_days:
        Optional shorter horizon, useful for chunked control / playback.
    time_offset_days:
        Added to the time axis of the returned dataframe so independently solved
        windows can be concatenated cleanly.
    controller_override:
        Optional instantiated controller. When omitted, the controller is built from
        `config.controller`.
    """
    ensure_dir(config.output_dir)
    controller = controller_override or build_controller(config.controller)
    model = SecondaryTreatmentModel(config, controller)
    y0 = initial_state_vector(config) if initial_state is None else np.asarray(initial_state, dtype=float)

    duration = float(duration_days if duration_days is not None else config.simulation.duration_days)
    n_points = max(2, int(duration * config.simulation.points_per_day) + 1)
    local_t_eval = np.linspace(0.0, duration, n_points)

    sol = solve_ivp(
        fun=model.rhs,
        t_span=(0.0, duration),
        y0=y0,
        t_eval=local_t_eval,
        method="LSODA",
        rtol=1e-6,
        atol=1e-8,
    )

    # Shift time after the solve so the ODE remains local to the current window.
    sol.t = sol.t + float(time_offset_days)
    df = _build_dataframe(config, model, sol)

    return SimulationResults(config=config, dataframe=df, solver_message=sol.message, success=sol.success)



def summarize_results(results: SimulationResults) -> pd.DataFrame:
    df = results.dataframe
    summary = {
        "scenario": results.config.scenario_name,
        "success": results.success,
        "final_NH4_mgN_L": df["S_NH4"].iloc[-1],
        "final_NO2_mgN_L": df["S_NO2"].iloc[-1],
        "final_NO3_mgN_L": df["S_NO3"].iloc[-1],
        "final_N2O_mgN_L": df["S_N2O"].iloc[-1],
        "avg_DO_mg_L": df["S_O2"].mean(),
        "peak_N2O_mgN_L": df["S_N2O"].max(),
        "cum_N2O_emitted_kgN": df["cum_n2o_emitted_kgN"].iloc[-1],
        "cum_aeration_energy": df["cum_aeration_energy"].iloc[-1],
    }
    return pd.DataFrame([summary])
