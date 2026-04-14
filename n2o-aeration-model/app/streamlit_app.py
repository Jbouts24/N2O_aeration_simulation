"""Streamlit UI for exploring the N2O aeration model.

The app keeps the scientific core in `src/n2o_model/*` and focuses only on:
- user controls,
- pseudo-live playback of precomputed trajectories,
- strategy comparison,
- a mock adaptive agent hook that can later be replaced by an LLM controller.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from streamlit_autorefresh import st_autorefresh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from n2o_model.interactive import (  # noqa: E402
    build_config_from_overrides,
    compare_strategies,
    latest_controller_message,
    run_controller_mode,
)
from n2o_model.parameters import ModelConfig  # noqa: E402
from n2o_model.scenarios import load_config  # noqa: E402


st.set_page_config(
    page_title="N2O Aeration Model Explorer",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded",
)


BASE_CONFIG_PATH = ROOT / "configs" / "base_case.yaml"
BASE_CONFIG = load_config(BASE_CONFIG_PATH)



def _init_state() -> None:
    defaults = {
        "run_result": None,
        "playback_index": 0,
        "playing": False,
        "compare_runs": None,
        "compare_summary": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value



def _build_overrides_from_sidebar(preset: str, controller_mode: str) -> tuple[dict, str]:
    """Read all sidebar widgets and convert them into a config override dict.

    Returns
    -------
    overrides, effective_controller_mode
        The effective mode can differ from the raw widget value when a quick preset
        is used (for example, selecting the fixed-high-DO preset).
    """
    controller_type = {
        "none / fixed": "fixed",
        "fixed": "fixed",
        "rule-based": "demand",
        "optimizer": "fixed",
        "agent placeholder": "fixed",
    }[controller_mode]

    low_do = st.session_state.low_do_setpoint
    med_do = st.session_state.medium_do_setpoint
    high_do = st.session_state.high_do_setpoint
    fixed_target = st.session_state.fixed_do_setpoint

    if preset == "fixed low DO":
        controller_mode = "fixed"
        fixed_target = low_do
    elif preset == "fixed medium DO":
        controller_mode = "fixed"
        fixed_target = med_do
    elif preset == "fixed high DO":
        controller_mode = "fixed"
        fixed_target = high_do
    elif preset == "dynamic rule-based":
        controller_mode = "rule-based"

    controller_type = {
        "none / fixed": "fixed",
        "fixed": "fixed",
        "rule-based": "demand",
        "optimizer": "fixed",
        "agent placeholder": "fixed",
    }[controller_mode]

    overrides = {
        "scenario_name": f"ui_{controller_mode.replace(' ', '_')}",
        "output_dir": "results/ui",
        "simulation": {
            "duration_days": float(st.session_state.sim_duration_days),
            "points_per_day": int(st.session_state.points_per_day),
        },
        "reactor": {
            "temperature_c": float(st.session_state.temperature_c),
            "pH": float(st.session_state.reactor_pH),
        },
        "influent": {
            "nh4_mgN_L": float(st.session_state.influent_nh4),
            "cod_mgCOD_L": float(st.session_state.influent_cod),
            "do_mgO2_L": float(st.session_state.influent_do),
        },
        "initial_conditions": {
            "do_mgO2_L": float(st.session_state.initial_do),
            "nh4_mgN_L": float(st.session_state.initial_nh4),
            "no2_mgN_L": float(st.session_state.initial_no2),
            "no3_mgN_L": float(st.session_state.initial_no3),
            "n2o_mgN_L": float(st.session_state.initial_n2o),
            "cod_mgCOD_L": float(st.session_state.initial_cod),
        },
        "biomass_initial": {
            "aob_mgCOD_L": float(st.session_state.aob_init),
            "nob_mgCOD_L": float(st.session_state.nob_init),
            "het_mgCOD_L": float(st.session_state.het_init),
        },
        "kinetics": {
            "nd_yield": float(st.session_state.nd_yield),
            "hao_yield": float(st.session_state.hao_yield),
            "den_n2o_yield_base": float(st.session_state.den_n2o_yield_base),
            "k_red_per_day": float(st.session_state.k_red_per_day),
        },
        "aeration": {
            "n2o_kla_factor": float(st.session_state.n2o_kla_factor),
            "energy_per_kla": float(st.session_state.energy_per_kla),
        },
        "controller": {
            "type": controller_type,
            "target_do_mg_L": float(fixed_target),
            "target_do_low_mg_L": float(low_do),
            "target_do_mid_mg_L": float(med_do),
            "target_do_high_mg_L": float(high_do),
            "nh4_low_mgN_L": float(st.session_state.rule_nh4_low),
            "nh4_high_mgN_L": float(st.session_state.rule_nh4_high),
            "kp": float(st.session_state.kp),
            "min_kla_per_day": float(st.session_state.min_kla),
            "max_kla_per_day": float(st.session_state.max_kla),
        },
        "optimization": {
            "setpoint_candidates_mg_L": [float(x) for x in st.session_state.optimizer_candidates.split(",") if x.strip()],
            "w_emission": float(st.session_state.w_emission),
            "w_energy": float(st.session_state.w_energy),
            "w_effluent_nh4": float(st.session_state.w_effluent_nh4),
        },
    }
    return overrides, controller_mode



def _line_figure(df: pd.DataFrame, y_cols: list[str], title: str, y_label: str, frame_df: pd.DataFrame | None = None) -> go.Figure:
    use_df = frame_df if frame_df is not None else df
    fig = go.Figure()
    for col in y_cols:
        fig.add_trace(go.Scatter(x=use_df["time_days"], y=use_df[col], mode="lines", name=col))
    fig.update_layout(title=title, xaxis_title="Time (days)", yaxis_title=y_label, height=350, margin=dict(l=20, r=20, t=50, b=20))
    return fig



def _comparison_bar(summary: pd.DataFrame, value_col: str, title: str, y_title: str) -> go.Figure:
    fig = px.bar(summary, x="display_strategy", y=value_col, color="display_strategy", title=title)
    fig.update_layout(showlegend=False, xaxis_title="Strategy", yaxis_title=y_title, height=350, margin=dict(l=20, r=20, t=50, b=20))
    return fig



def _export_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")



def _render_sidebar() -> tuple[ModelConfig, str, str, float, int]:
    st.sidebar.title("Model controls")
    st.sidebar.caption("Adjust parameters, choose a controller mode, then run or compare scenarios.")

    st.sidebar.selectbox(
        "Quick scenario preset",
        ["custom", "fixed low DO", "fixed medium DO", "fixed high DO", "dynamic rule-based"],
        key="scenario_preset",
    )
    st.sidebar.selectbox(
        "Controller mode",
        ["fixed", "rule-based", "optimizer", "agent placeholder"],
        key="controller_mode",
    )

    with st.sidebar.expander("Influent", expanded=True):
        st.number_input("Influent NH4-N (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.influent.nh4_mgN_L), key="influent_nh4")
        st.number_input("Influent COD (mgCOD/L)", min_value=0.0, value=float(BASE_CONFIG.influent.cod_mgCOD_L), key="influent_cod")
        st.number_input("Influent DO (mgO2/L)", min_value=0.0, value=float(BASE_CONFIG.influent.do_mgO2_L), key="influent_do")
        st.number_input("Initial reactor NH4-N (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.initial_conditions.nh4_mgN_L), key="initial_nh4")
        st.number_input("Initial reactor NO2-N (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.initial_conditions.no2_mgN_L), key="initial_no2")
        st.number_input("Initial reactor NO3-N (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.initial_conditions.no3_mgN_L), key="initial_no3")
        st.number_input("Initial dissolved N2O-N (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.initial_conditions.n2o_mgN_L), key="initial_n2o", format="%.4f")
        st.number_input("Initial reactor COD (mgCOD/L)", min_value=0.0, value=float(BASE_CONFIG.initial_conditions.cod_mgCOD_L), key="initial_cod")
        st.number_input("Initial DO (mgO2/L)", min_value=0.0, value=float(BASE_CONFIG.initial_conditions.do_mgO2_L), key="initial_do")

    with st.sidebar.expander("Biology", expanded=False):
        st.number_input("Initial AOB biomass (mgCOD/L)", min_value=0.0, value=float(BASE_CONFIG.biomass_initial.aob_mgCOD_L), key="aob_init")
        st.number_input("Initial NOB biomass (mgCOD/L)", min_value=0.0, value=float(BASE_CONFIG.biomass_initial.nob_mgCOD_L), key="nob_init")
        st.number_input("Initial HET biomass (mgCOD/L)", min_value=0.0, value=float(BASE_CONFIG.biomass_initial.het_mgCOD_L), key="het_init")
        st.number_input("Temperature (°C)", min_value=5.0, max_value=35.0, value=float(BASE_CONFIG.reactor.temperature_c), key="temperature_c")
        st.number_input("pH", min_value=5.0, max_value=9.5, value=float(BASE_CONFIG.reactor.pH), key="reactor_pH", format="%.2f")

    with st.sidebar.expander("N2O pathways", expanded=False):
        st.number_input("AOB low-DO N2O yield (nd_yield)", min_value=0.0, value=float(BASE_CONFIG.kinetics.nd_yield), key="nd_yield", format="%.4f")
        st.number_input("AOB oxygenated N2O yield (hao_yield)", min_value=0.0, value=float(BASE_CONFIG.kinetics.hao_yield), key="hao_yield", format="%.5f")
        st.number_input("Base denitrifier N2O yield", min_value=0.0, value=float(BASE_CONFIG.kinetics.den_n2o_yield_base), key="den_n2o_yield_base", format="%.4f")
        st.number_input("N2O reduction rate k_red (1/day)", min_value=0.0, value=float(BASE_CONFIG.kinetics.k_red_per_day), key="k_red_per_day", format="%.4f")

    with st.sidebar.expander("Aeration / control", expanded=True):
        st.number_input("Fixed DO setpoint (mg/L)", min_value=0.0, max_value=6.0, value=float(BASE_CONFIG.controller.target_do_mg_L), key="fixed_do_setpoint", format="%.2f")
        st.number_input("Low DO strategy setpoint (mg/L)", min_value=0.0, max_value=6.0, value=0.5, key="low_do_setpoint", format="%.2f")
        st.number_input("Medium DO strategy setpoint (mg/L)", min_value=0.0, max_value=6.0, value=1.5, key="medium_do_setpoint", format="%.2f")
        st.number_input("High DO strategy setpoint (mg/L)", min_value=0.0, max_value=6.0, value=3.0, key="high_do_setpoint", format="%.2f")
        st.number_input("Rule-based NH4 low threshold (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.controller.nh4_low_mgN_L), key="rule_nh4_low")
        st.number_input("Rule-based NH4 high threshold (mgN/L)", min_value=0.0, value=float(BASE_CONFIG.controller.nh4_high_mgN_L), key="rule_nh4_high")
        st.number_input("DO control gain kp", min_value=0.1, value=float(BASE_CONFIG.controller.kp), key="kp")
        st.number_input("Minimum kLa (1/day)", min_value=0.0, value=float(BASE_CONFIG.controller.min_kla_per_day), key="min_kla")
        st.number_input("Maximum kLa (1/day)", min_value=1.0, value=float(BASE_CONFIG.controller.max_kla_per_day), key="max_kla")
        st.number_input("N2O stripping factor", min_value=0.0, value=float(BASE_CONFIG.aeration.n2o_kla_factor), key="n2o_kla_factor", format="%.4f")
        st.number_input("Aeration energy per kLa", min_value=0.0, value=float(BASE_CONFIG.aeration.energy_per_kla), key="energy_per_kla", format="%.3f")

    with st.sidebar.expander("Simulation settings", expanded=False):
        st.number_input("Simulation length (days)", min_value=0.1, value=float(BASE_CONFIG.simulation.duration_days), key="sim_duration_days")
        st.number_input("Points per day", min_value=24, max_value=2000, value=int(BASE_CONFIG.simulation.points_per_day), step=24, key="points_per_day")
        st.number_input("Agent decision interval (days)", min_value=0.01, max_value=0.5, value=0.05, key="agent_interval", format="%.3f")
        st.slider("Playback interval (ms)", min_value=100, max_value=1000, value=250, step=50, key="playback_interval_ms")
        st.slider("Playback stride (rows per refresh)", min_value=1, max_value=20, value=4, key="playback_stride")

    with st.sidebar.expander("Optimizer objective", expanded=False):
        st.text_input("Candidate DO setpoints (comma-separated)", value="0.5,1.0,1.5,2.0,2.5,3.0", key="optimizer_candidates")
        st.number_input("Weight: N2O emission", min_value=0.0, value=float(BASE_CONFIG.optimization.w_emission), key="w_emission")
        st.number_input("Weight: energy", min_value=0.0, value=float(BASE_CONFIG.optimization.w_energy), key="w_energy")
        st.number_input("Weight: effluent NH4", min_value=0.0, value=float(BASE_CONFIG.optimization.w_effluent_nh4), key="w_effluent_nh4")

    overrides, effective_mode = _build_overrides_from_sidebar(st.session_state.scenario_preset, st.session_state.controller_mode)
    cfg = build_config_from_overrides(BASE_CONFIG, overrides)
    return cfg, effective_mode, st.session_state.scenario_preset, float(st.session_state.agent_interval), int(st.session_state.playback_stride)



def _run_current_mode(config: ModelConfig, controller_mode: str, agent_interval: float) -> None:
    with st.spinner("Running simulation..."):
        result = run_controller_mode(config, mode=controller_mode, decision_interval_days=agent_interval)
    st.session_state.run_result = result
    st.session_state.playback_index = 0
    st.session_state.playing = False



def _current_frame_df() -> tuple[pd.DataFrame | None, pd.DataFrame | None]:
    run = st.session_state.run_result
    if run is None:
        return None, None
    full_df = run.results.dataframe
    idx = min(st.session_state.playback_index, len(full_df) - 1)
    return full_df, full_df.iloc[: idx + 1].copy()



def _render_single_run(config: ModelConfig, controller_mode: str, agent_interval: float, playback_stride: int) -> None:
    st.header("Single-run explorer")
    action_cols = st.columns([1, 1, 1, 1])
    if action_cols[0].button("Run simulation", use_container_width=True):
        _run_current_mode(config, controller_mode, agent_interval)
    if action_cols[1].button("Start / resume", use_container_width=True, disabled=st.session_state.run_result is None):
        st.session_state.playing = True
    if action_cols[2].button("Pause", use_container_width=True, disabled=st.session_state.run_result is None):
        st.session_state.playing = False
    if action_cols[3].button("Reset playback", use_container_width=True, disabled=st.session_state.run_result is None):
        st.session_state.playback_index = 0
        st.session_state.playing = False

    if st.session_state.run_result is None:
        st.info("Set parameters in the sidebar, then click **Run simulation**.")
        return

    run = st.session_state.run_result
    full_df, frame_df = _current_frame_df()
    assert full_df is not None and frame_df is not None

    if st.session_state.playing:
        st_autorefresh(interval=int(st.session_state.playback_interval_ms), key="playback_refresh")
        if st.session_state.playback_index < len(full_df) - 1:
            st.session_state.playback_index = min(len(full_df) - 1, st.session_state.playback_index + playback_stride)
        else:
            st.session_state.playing = False

    current = frame_df.iloc[-1]
    metrics = st.columns(5)
    metrics[0].metric("Time", f"{current['time_days']:.2f} d")
    metrics[1].metric("Current NH4", f"{current['S_NH4']:.2f} mgN/L")
    metrics[2].metric("Current N2O", f"{current['S_N2O']:.4f} mgN/L")
    metrics[3].metric("Cum. N2O emitted", f"{current['cum_n2o_emitted_kgN']:.3f} kgN")
    metrics[4].metric("Aeration energy", f"{current['cum_aeration_energy']:.2f}")

    st.caption(latest_controller_message(run, frame_index=st.session_state.playback_index))

    tabs = st.tabs(["Species", "DO & control", "Biomass & energy", "Controller log / export"])
    with tabs[0]:
        fig = _line_figure(frame_df, ["S_NH4", "S_NO2", "S_NO3", "S_N2O"], "Nitrogen species and dissolved N2O", "mg/L")
        st.plotly_chart(fig, use_container_width=True)
        emission_fig = _line_figure(frame_df, ["n2o_emission_rate_kgN_d", "cum_n2o_emitted_kgN"], "N2O emission rate and cumulative emissions", "kgN/d or kgN")
        st.plotly_chart(emission_fig, use_container_width=True)

    with tabs[1]:
        fig = _line_figure(frame_df, ["S_O2", "target_do", "kla_o2_per_day"], "DO, target DO, and aeration effort", "mg/L or 1/day")
        st.plotly_chart(fig, use_container_width=True)
        env_df = frame_df[["time_days", "pH", "temperature_c"]].copy()
        env_fig = _line_figure(env_df, ["pH", "temperature_c"], "Fixed environmental inputs", "units as shown")
        st.plotly_chart(env_fig, use_container_width=True)
        st.caption("In v1, pH and temperature are fixed inputs rather than dynamic states, so their traces are constant over time.")

    with tabs[2]:
        fig = _line_figure(frame_df, ["X_AOB", "X_NOB", "X_HET"], "Biomass states", "mgCOD/L")
        st.plotly_chart(fig, use_container_width=True)
        energy_fig = _line_figure(frame_df, ["energy_rate", "cum_aeration_energy"], "Aeration energy proxy", "arbitrary units")
        st.plotly_chart(energy_fig, use_container_width=True)

    with tabs[3]:
        if run.controller_log is not None:
            st.dataframe(run.controller_log, use_container_width=True, hide_index=True)
        elif run.optimization_table is not None:
            st.dataframe(run.optimization_table, use_container_width=True, hide_index=True)
        else:
            st.write("No discrete controller log for this mode; the trace above reflects the selected continuous controller.")

        st.download_button(
            "Download current run as CSV",
            data=_export_csv_bytes(full_df),
            file_name=f"{run.results.config.scenario_name}_timeseries.csv",
            mime="text/csv",
            use_container_width=True,
        )



def _render_comparison(config: ModelConfig) -> None:
    st.header("Strategy comparison")
    st.caption("Run a bundle of strategies using the current sidebar parameters. This keeps the same biology and influent while changing only the aeration/control strategy.")
    default_strategies = ["fixed low DO", "fixed medium DO", "fixed high DO", "dynamic rule-based", "optimizer-enabled"]
    selected = st.multiselect(
        "Strategies",
        options=default_strategies,
        default=default_strategies,
        help="The optimizer-enabled option runs the grid-search layer and includes the best fixed-DO candidate.",
    )
    if st.button("Run comparison", use_container_width=False):
        with st.spinner("Running scenario bundle..."):
            runs, summary = compare_strategies(
                config,
                strategies=selected,
                low_do=float(st.session_state.low_do_setpoint),
                medium_do=float(st.session_state.medium_do_setpoint),
                high_do=float(st.session_state.high_do_setpoint),
            )
        st.session_state.compare_runs = runs
        st.session_state.compare_summary = summary

    if st.session_state.compare_summary is None or st.session_state.compare_runs is None:
        st.info("Select strategies and click **Run comparison**.")
        return

    summary: pd.DataFrame = st.session_state.compare_summary
    runs: dict[str, any] = st.session_state.compare_runs
    st.dataframe(summary, use_container_width=True, hide_index=True)

    c1, c2 = st.columns(2)
    c1.plotly_chart(_comparison_bar(summary, "cum_N2O_emitted_kgN", "Cumulative N2O emitted", "kgN"), use_container_width=True)
    c2.plotly_chart(_comparison_bar(summary, "cum_aeration_energy", "Cumulative aeration energy", "arbitrary units"), use_container_width=True)

    summary_long = summary[["display_strategy", "final_NH4_mgN_L", "final_NO3_mgN_L", "objective_score"]].melt(
        id_vars="display_strategy", var_name="metric", value_name="value"
    )
    fig = px.bar(summary_long, x="display_strategy", y="value", color="metric", barmode="group", title="Effluent quality and objective score")
    fig.update_layout(height=400, margin=dict(l=20, r=20, t=50, b=20))
    st.plotly_chart(fig, use_container_width=True)

    compare_metric = st.selectbox(
        "Overlay timeseries for comparison",
        ["S_NH4", "S_NO2", "S_NO3", "S_N2O", "S_O2", "n2o_emission_rate_kgN_d", "cum_n2o_emitted_kgN", "cum_aeration_energy"],
        index=5,
    )
    overlay = go.Figure()
    for label, result in runs.items():
        df = result.dataframe
        overlay.add_trace(go.Scatter(x=df["time_days"], y=df[compare_metric], mode="lines", name=label))
    overlay.update_layout(
        title=f"Comparison of {compare_metric}",
        xaxis_title="Time (days)",
        yaxis_title=compare_metric,
        height=420,
        margin=dict(l=20, r=20, t=50, b=20),
    )
    st.plotly_chart(overlay, use_container_width=True)



def _render_agent_hook_notes() -> None:
    st.header("Future agent / LLM hook")
    st.write(
        "The current **agent placeholder** mode already uses a stepwise observe-decide-act loop. "
        "That same interface can later be swapped for a real LLM or policy model without changing the ODE core."
    )
    st.markdown(
        """
        **Current placeholder loop**
        1. Observe the latest reactor state.
        2. Produce a DO target and a plain-language reason.
        3. Simulate the next time chunk with that target.
        4. Repeat.

        **How to replace it later**
        - Keep the same state summary schema.
        - Replace the heuristic decision function with an LLM/tool call or policy model.
        - Return a structured response such as `{target_do_mg_L, rationale, confidence}`.
        - Preserve guardrails (setpoint bounds, max step changes, fallback fixed DO).
        """
    )



def main() -> None:
    _init_state()
    config, controller_mode, preset, agent_interval, playback_stride = _render_sidebar()

    st.title("💧 N2O aeration model explorer")
    st.write(
        "This Streamlit app wraps the existing ODE-based wastewater N2O model with interactive controls, "
        "pseudo-live playback, scenario comparison, and a mock adaptive controller hook."
    )
    st.caption(f"Current preset: **{preset}** · Current controller mode: **{controller_mode}**")

    tabs = st.tabs(["Single run", "Strategy comparison", "Agent/LLM hook"])
    with tabs[0]:
        _render_single_run(config, controller_mode, agent_interval, playback_stride)
    with tabs[1]:
        _render_comparison(config)
    with tabs[2]:
        _render_agent_hook_notes()


if __name__ == "__main__":
    main()
