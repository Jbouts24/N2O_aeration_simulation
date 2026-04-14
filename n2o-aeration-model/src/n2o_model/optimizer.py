"""Simple optimization / control layer for the repository."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .parameters import ModelConfig
from .simulator import SimulationResults, run_simulation


@dataclass
class OptimizationResult:
    best_config: ModelConfig
    best_results: SimulationResults
    candidate_table: pd.DataFrame



def objective_value(results: SimulationResults, config: ModelConfig) -> float:
    df = results.dataframe
    opt = config.optimization
    final_emission = float(df["cum_n2o_emitted_kgN"].iloc[-1])
    final_energy = float(df["cum_aeration_energy"].iloc[-1])
    terminal_nh4 = float(df["S_NH4"].tail(max(5, len(df) // 10)).mean())
    return opt.w_emission * final_emission + opt.w_energy * final_energy + opt.w_effluent_nh4 * terminal_nh4



def optimize_fixed_do_setpoints(config: ModelConfig) -> OptimizationResult:
    rows = []
    best_score = float("inf")
    best_cfg = None
    best_results = None

    for setpoint in config.optimization.setpoint_candidates_mg_L:
        candidate_cfg = config.with_updates(
            {
                "scenario_name": f"opt_fixed_do_{setpoint:.2f}",
                "output_dir": f"results/opt_fixed_do_{setpoint:.2f}",
                "controller": {"type": "fixed", "target_do_mg_L": float(setpoint)},
            }
        )
        results = run_simulation(candidate_cfg)
        score = objective_value(results, candidate_cfg)
        summary = {
            "scenario": candidate_cfg.scenario_name,
            "target_do_mg_L": setpoint,
            "objective": score,
            "cum_N2O_emitted_kgN": float(results.dataframe["cum_n2o_emitted_kgN"].iloc[-1]),
            "cum_aeration_energy": float(results.dataframe["cum_aeration_energy"].iloc[-1]),
            "terminal_NH4_mgN_L": float(results.dataframe["S_NH4"].tail(max(5, len(results.dataframe) // 10)).mean()),
        }
        rows.append(summary)
        if score < best_score:
            best_score = score
            best_cfg = candidate_cfg
            best_results = results

    candidate_table = pd.DataFrame(rows).sort_values("objective", ascending=True).reset_index(drop=True)
    assert best_cfg is not None and best_results is not None
    return OptimizationResult(best_config=best_cfg, best_results=best_results, candidate_table=candidate_table)
