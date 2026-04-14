"""Plotting helpers for single-scenario and multi-scenario outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib.pyplot as plt
import pandas as pd

from .simulator import SimulationResults
from .utils import ensure_dir



def _savefig(path: Path) -> None:
    plt.tight_layout()
    plt.savefig(path, dpi=160)
    plt.close()



def plot_timeseries_bundle(results: SimulationResults, output_dir: str | Path) -> None:
    out_dir = ensure_dir(output_dir)
    df = results.dataframe
    name = results.config.scenario_name

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_days"], df["S_NH4"], label="NH4-N")
    plt.plot(df["time_days"], df["S_NO2"], label="NO2-N")
    plt.plot(df["time_days"], df["S_NO3"], label="NO3-N")
    plt.plot(df["time_days"], df["S_N2O"], label="dissolved N2O-N")
    plt.xlabel("Time (days)")
    plt.ylabel("Concentration (mg/L)")
    plt.title(f"Nitrogen species: {name}")
    plt.legend()
    _savefig(out_dir / f"{name}_nitrogen_species.png")

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_days"], df["X_AOB"], label="AOB")
    plt.plot(df["time_days"], df["X_NOB"], label="NOB")
    plt.plot(df["time_days"], df["X_HET"], label="HET")
    plt.xlabel("Time (days)")
    plt.ylabel("Biomass (mgCOD/L)")
    plt.title(f"Biomass states: {name}")
    plt.legend()
    _savefig(out_dir / f"{name}_biomass.png")

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_days"], df["S_O2"], label="DO")
    plt.plot(df["time_days"], df["target_do"], label="DO target", linestyle="--")
    plt.xlabel("Time (days)")
    plt.ylabel("DO (mg/L)")
    plt.title(f"Dissolved oxygen: {name}")
    plt.legend()
    _savefig(out_dir / f"{name}_do.png")

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_days"], df["n2o_emission_rate_kgN_d"], label="N2O emission rate (kgN/d)")
    plt.plot(df["time_days"], df["cum_n2o_emitted_kgN"], label="Cumulative emitted N2O-N (kg)")
    plt.xlabel("Time (days)")
    plt.ylabel("Emissions")
    plt.title(f"N2O emissions: {name}")
    plt.legend()
    _savefig(out_dir / f"{name}_n2o_emissions.png")

    plt.figure(figsize=(10, 5))
    plt.plot(df["time_days"], df["energy_rate"], label="Aeration energy proxy rate")
    plt.plot(df["time_days"], df["cum_aeration_energy"], label="Cumulative aeration energy proxy")
    plt.xlabel("Time (days)")
    plt.ylabel("Energy proxy")
    plt.title(f"Aeration effort: {name}")
    plt.legend()
    _savefig(out_dir / f"{name}_aeration_energy.png")



def plot_scenario_comparison(runs: Iterable[tuple[str, SimulationResults]], output_dir: str | Path) -> None:
    out_dir = ensure_dir(output_dir)
    runs = list(runs)

    plt.figure(figsize=(10, 5))
    for name, results in runs:
        df = results.dataframe
        plt.plot(df["time_days"], df["n2o_emission_rate_kgN_d"], label=name)
    plt.xlabel("Time (days)")
    plt.ylabel("N2O emission rate (kgN/d)")
    plt.title("N2O emission-rate comparison")
    plt.legend()
    _savefig(out_dir / "comparison_n2o_emission_rate.png")

    plt.figure(figsize=(10, 5))
    for name, results in runs:
        df = results.dataframe
        plt.plot(df["time_days"], df["S_O2"], label=name)
    plt.xlabel("Time (days)")
    plt.ylabel("DO (mg/L)")
    plt.title("DO comparison")
    plt.legend()
    _savefig(out_dir / "comparison_do.png")

    summary_rows = []
    for name, results in runs:
        df = results.dataframe
        summary_rows.append(
            {
                "scenario": name,
                "cum_n2o_emitted_kgN": float(df["cum_n2o_emitted_kgN"].iloc[-1]),
                "cum_aeration_energy": float(df["cum_aeration_energy"].iloc[-1]),
                "final_nh4_mgN_L": float(df["S_NH4"].iloc[-1]),
            }
        )
    summary = pd.DataFrame(summary_rows)
    summary.to_csv(out_dir / "comparison_summary.csv", index=False)

    plt.figure(figsize=(9, 5))
    plt.bar(summary["scenario"], summary["cum_n2o_emitted_kgN"])
    plt.ylabel("Cumulative N2O emitted (kgN)")
    plt.title("Cumulative N2O comparison")
    _savefig(out_dir / "comparison_cumulative_n2o.png")

    plt.figure(figsize=(9, 5))
    plt.bar(summary["scenario"], summary["cum_aeration_energy"])
    plt.ylabel("Cumulative aeration energy proxy")
    plt.title("Aeration energy comparison")
    _savefig(out_dir / "comparison_cumulative_energy.png")
