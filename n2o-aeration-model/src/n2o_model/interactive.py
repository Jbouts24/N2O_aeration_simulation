"""Helpers for the interactive Streamlit application.

This module keeps the UI thin by collecting reusable logic for:
- running one of several controller modes,
- executing a piecewise adaptive "agent placeholder" controller,
- preparing comparison scenarios for the dashboard.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import numpy as np
import pandas as pd

from .optimizer import OptimizationResult, objective_value, optimize_fixed_do_setpoints
from .parameters import ModelConfig
from .simulator import SimulationResults, run_simulation, summarize_results
from .states import STATE_NAMES, state_to_dict


@dataclass
class InteractiveRunResult:
    """Container returned to the UI layer."""

    mode: str
    display_name: str
    results: SimulationResults
    controller_log: pd.DataFrame | None = None
    optimization_table: pd.DataFrame | None = None



def build_config_from_overrides(base_config: ModelConfig, overrides: dict) -> ModelConfig:
    """Apply nested updates to a base config and return a new config."""
    return base_config.with_updates(overrides)



def _recompute_cumulative_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Recompute cumulative outputs after concatenating multiple simulation chunks."""
    out = df.copy()
    time = out["time_days"].to_numpy(dtype=float)
    if len(out) == 0:
        return out
    out["cum_n2o_emitted_kgN"] = np.concatenate(
        [[0.0], np.cumtrapz(out["n2o_emission_rate_kgN_d"].to_numpy(dtype=float), time)]
    ) if hasattr(np, 'cumtrapz') else out["cum_n2o_emitted_kgN"]
    # NumPy does not expose cumtrapz in all versions, so use a manual trapezoid.
    if not hasattr(np, 'cumtrapz'):
        dt = np.diff(time)
        vals = out["n2o_emission_rate_kgN_d"].to_numpy(dtype=float)
        cum = np.zeros(len(out), dtype=float)
        if len(out) > 1:
            cum[1:] = np.cumsum(0.5 * (vals[:-1] + vals[1:]) * dt)
        out["cum_n2o_emitted_kgN"] = cum

    energy_vals = out["energy_rate"].to_numpy(dtype=float)
    energy_cum = np.zeros(len(out), dtype=float)
    if len(out) > 1:
        energy_cum[1:] = np.cumsum(0.5 * (energy_vals[:-1] + energy_vals[1:]) * np.diff(time))
    out["cum_aeration_energy"] = energy_cum
    return out



def _mock_agent_decision(
    state: dict[str, float],
    previous_setpoint: float,
    config: ModelConfig,
) -> tuple[float, str]:
    """Heuristic controller that behaves adaptively and narrates its choices.

    This is intentionally *not* an LLM. It is a transparent placeholder that:
    - raises DO when NH4 or NO2 are high,
    - holds or modestly increases DO when N2O + NO2 suggest nitrifier stress,
    - lowers DO when the reactor is well-polished to save energy.
    """
    s_nh4 = float(state["S_NH4"])
    s_no2 = float(state["S_NO2"])
    s_n2o = float(state["S_N2O"])
    s_do = float(state["S_O2"])

    low = config.controller.target_do_low_mg_L
    mid = config.controller.target_do_mid_mg_L
    high = config.controller.target_do_high_mg_L
    step_up = 0.35
    step_down = 0.25

    if s_nh4 > config.controller.nh4_high_mgN_L or s_no2 > 1.0:
        target = min(high, max(previous_setpoint, mid) + step_up)
        reason = (
            f"Raising DO because NH4 ({s_nh4:.2f} mgN/L) or NO2 ({s_no2:.2f} mgN/L) is high, "
            "suggesting incomplete oxidation and elevated N2O risk."
        )
    elif s_n2o > 0.08 and s_no2 > 0.3:
        target = min(high, previous_setpoint + 0.20)
        reason = (
            f"Increasing DO slightly because dissolved N2O ({s_n2o:.3f} mgN/L) and NO2 ({s_no2:.2f} mgN/L) "
            "suggest nitrifier-denitrification stress."
        )
    elif s_nh4 < config.controller.nh4_low_mgN_L and s_no2 < 0.2 and s_do > low:
        target = max(low, previous_setpoint - step_down)
        reason = (
            f"Lowering DO to save aeration energy because NH4 ({s_nh4:.2f} mgN/L) and NO2 ({s_no2:.2f} mgN/L) are low."
        )
    else:
        target = mid if abs(previous_setpoint - mid) < 0.1 else previous_setpoint + np.sign(mid - previous_setpoint) * 0.1
        target = float(min(high, max(low, target)))
        reason = (
            f"Holding or gently nudging DO toward the middle operating band; current DO is {s_do:.2f} mg/L."
        )

    return float(min(high, max(low, target))), reason



def run_agent_placeholder(
    config: ModelConfig,
    decision_interval_days: float = 0.05,
) -> InteractiveRunResult:
    """Run the model piecewise with a mock adaptive controller.

    Each chunk is simulated using the existing ODE engine with a fixed DO target for
    that chunk. After the chunk completes, the next DO target is selected from the new
    observed states. This creates a transparent stepping stone toward future agentic
    or LLM-driven control.
    """
    total_duration = config.simulation.duration_days
    current_time = 0.0
    current_state = None
    previous_setpoint = float(config.controller.target_do_mg_L)

    frames: list[pd.DataFrame] = []
    decisions: list[dict[str, float | str]] = []
    messages: list[str] = []
    success = True

    while current_time < total_duration - 1e-12:
        state_dict = state_to_dict(current_state) if current_state is not None else state_to_dict(
            np.array(
                [
                    config.initial_conditions.nh4_mgN_L,
                    config.initial_conditions.no2_mgN_L,
                    config.initial_conditions.no3_mgN_L,
                    config.initial_conditions.n2o_mgN_L,
                    config.initial_conditions.cod_mgCOD_L,
                    config.initial_conditions.do_mgO2_L,
                    config.biomass_initial.aob_mgCOD_L,
                    config.biomass_initial.nob_mgCOD_L,
                    config.biomass_initial.het_mgCOD_L,
                ],
                dtype=float,
            )
        )
        target, reason = _mock_agent_decision(state_dict, previous_setpoint, config)
        chunk_duration = min(decision_interval_days, total_duration - current_time)

        segment_cfg = config.with_updates(
            {
                "scenario_name": config.scenario_name,
                "controller": {"type": "fixed", "target_do_mg_L": float(target)},
            }
        )
        seg = run_simulation(
            segment_cfg,
            initial_state=current_state,
            duration_days=chunk_duration,
            time_offset_days=current_time,
        )
        seg_df = seg.dataframe.copy()
        if frames:
            seg_df = seg_df.iloc[1:].reset_index(drop=True)
        frames.append(seg_df)
        messages.append(seg.solver_message)
        success = success and seg.success

        last_row = seg.dataframe.iloc[-1]
        current_state = last_row[STATE_NAMES].to_numpy(dtype=float)
        current_time += chunk_duration
        decisions.append(
            {
                "time_days": float(seg.dataframe["time_days"].iloc[0]),
                "target_do_mg_L": float(target),
                "S_NH4": float(last_row["S_NH4"]),
                "S_NO2": float(last_row["S_NO2"]),
                "S_N2O": float(last_row["S_N2O"]),
                "S_O2": float(last_row["S_O2"]),
                "reason": reason,
            }
        )
        previous_setpoint = target

    combined_df = pd.concat(frames, ignore_index=True)
    combined_df = _recompute_cumulative_columns(combined_df)
    results = SimulationResults(
        config=config.with_updates({"controller": {"type": "agent_placeholder"}}),
        dataframe=combined_df,
        solver_message=" | ".join(messages),
        success=success,
    )
    controller_log = pd.DataFrame(decisions)
    return InteractiveRunResult(
        mode="agent_placeholder",
        display_name="Mock adaptive agent",
        results=results,
        controller_log=controller_log,
    )



def run_controller_mode(
    config: ModelConfig,
    mode: str,
    decision_interval_days: float = 0.05,
) -> InteractiveRunResult:
    """Execute one of the UI-exposed controller modes."""
    normalized = mode.strip().lower()
    if normalized in {"fixed", "none", "none / fixed"}:
        results = run_simulation(config.with_updates({"controller": {"type": "fixed"}}))
        return InteractiveRunResult(mode="fixed", display_name="Fixed DO", results=results)

    if normalized in {"rule-based", "rule_based", "dynamic", "demand"}:
        results = run_simulation(config.with_updates({"controller": {"type": "demand"}}))
        return InteractiveRunResult(mode="rule_based", display_name="Dynamic rule-based DO", results=results)

    if normalized in {"optimizer", "optimization"}:
        opt: OptimizationResult = optimize_fixed_do_setpoints(config)
        return InteractiveRunResult(
            mode="optimizer",
            display_name=f"Optimizer best fixed DO ({opt.best_config.controller.target_do_mg_L:.2f} mg/L)",
            results=opt.best_results,
            optimization_table=opt.candidate_table,
        )

    if normalized in {"agent", "agent placeholder", "agent_placeholder"}:
        return run_agent_placeholder(config, decision_interval_days=decision_interval_days)

    raise ValueError(f"Unknown controller mode: {mode}")



def build_strategy_configs(
    base_config: ModelConfig,
    low_do: float = 0.5,
    medium_do: float = 1.5,
    high_do: float = 3.0,
) -> dict[str, ModelConfig]:
    """Create a standard suite of comparison strategies from the current UI state."""
    return {
        "fixed low DO": base_config.with_updates(
            {
                "scenario_name": "ui_low_do",
                "controller": {"type": "fixed", "target_do_mg_L": float(low_do)},
            }
        ),
        "fixed medium DO": base_config.with_updates(
            {
                "scenario_name": "ui_medium_do",
                "controller": {"type": "fixed", "target_do_mg_L": float(medium_do)},
            }
        ),
        "fixed high DO": base_config.with_updates(
            {
                "scenario_name": "ui_high_do",
                "controller": {"type": "fixed", "target_do_mg_L": float(high_do)},
            }
        ),
        "dynamic rule-based": base_config.with_updates(
            {
                "scenario_name": "ui_dynamic_do",
                "controller": {
                    "type": "demand",
                    "target_do_low_mg_L": float(low_do),
                    "target_do_mid_mg_L": float(medium_do),
                    "target_do_high_mg_L": float(high_do),
                },
            }
        ),
    }



def compare_strategies(
    base_config: ModelConfig,
    strategies: Iterable[str],
    low_do: float = 0.5,
    medium_do: float = 1.5,
    high_do: float = 3.0,
    include_optimizer: bool = False,
) -> tuple[dict[str, SimulationResults], pd.DataFrame]:
    """Run a suite of scenarios and return both trajectories and a summary table."""
    strategy_map = build_strategy_configs(base_config, low_do=low_do, medium_do=medium_do, high_do=high_do)
    runs: dict[str, SimulationResults] = {}
    rows: list[pd.DataFrame] = []

    for strategy in strategies:
        if strategy == "optimizer-enabled":
            opt = optimize_fixed_do_setpoints(base_config)
            runs[strategy] = opt.best_results
            summary = summarize_results(opt.best_results)
            summary.insert(0, "display_strategy", strategy)
            summary["objective_score"] = objective_value(opt.best_results, opt.best_config)
            rows.append(summary)
            continue

        cfg = strategy_map[strategy]
        results = run_simulation(cfg)
        runs[strategy] = results
        summary = summarize_results(results)
        summary.insert(0, "display_strategy", strategy)
        summary["objective_score"] = objective_value(results, cfg)
        rows.append(summary)

    summary_table = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()
    return runs, summary_table



def latest_controller_message(run: InteractiveRunResult, frame_index: int | None = None) -> str:
    """Return a human-readable current controller explanation for display in the UI."""
    if run.mode == "agent_placeholder" and run.controller_log is not None and not run.controller_log.empty:
        if frame_index is None:
            row = run.controller_log.iloc[-1]
        else:
            frame_time = float(run.results.dataframe.iloc[min(frame_index, len(run.results.dataframe) - 1)]["time_days"])
            eligible = run.controller_log[run.controller_log["time_days"] <= frame_time]
            row = eligible.iloc[-1] if not eligible.empty else run.controller_log.iloc[0]
        return f"Target DO {row['target_do_mg_L']:.2f} mg/L. {row['reason']}"

    if run.mode == "optimizer" and run.optimization_table is not None and not run.optimization_table.empty:
        best = run.optimization_table.iloc[0]
        return (
            f"Grid search selected a fixed DO setpoint of {best['target_do_mg_L']:.2f} mg/L "
            f"with objective score {best['objective']:.3f}."
        )

    if run.mode == "rule_based":
        return "Dynamic rule-based control is adjusting the DO target using the NH4 thresholds in the controller settings."

    target = run.results.dataframe["target_do"].iloc[min(frame_index or 0, len(run.results.dataframe) - 1)]
    return f"Fixed control mode. Current DO target is {target:.2f} mg/L."
