# n2o-aeration-model

A modular Python repository for simulating the qualitative effect of aeration strategy on N2O dynamics in secondary wastewater treatment.

## What this repository does

This v1/v2 repository combines:

- a **semi-mechanistic, deterministic ODE model** for nitrogen and N2O dynamics,
- a **baseline CLI workflow** for scenarios and comparisons,
- a **simple optimization layer** over fixed DO setpoints,
- a **Streamlit exploration app** with live-looking playback, parameter sliders, strategy comparison, and a mock adaptive agent hook.

The reactor model tracks:

- NH4-N (`S_NH4`)
- NO2-N (`S_NO2`)
- NO3-N (`S_NO3`)
- dissolved N2O-N (`S_N2O`)
- readily biodegradable COD (`S_COD`)
- dissolved oxygen (`S_O2`)
- AOB biomass (`X_AOB`)
- NOB biomass (`X_NOB`)
- heterotrophic denitrifier biomass (`X_HET`)

It includes:

- AOB nitrification
- NOB nitrite oxidation
- AOB-linked N2O production under low DO / elevated nitrite (nitrifier denitrification surrogate)
- a smaller oxygenated AOB-linked hydroxylamine surrogate
- heterotrophic denitrification as both an N2O source and an N2O sink
- N2O stripping during aeration
- fixed-DO control
- demand-based rule control
- optimizer selection of a best fixed DO setpoint
- a mock adaptive "agent placeholder" controller that can later be replaced with an LLM or policy model

## Why Streamlit for the interface

For this repository, **Streamlit** is the best v1 choice because it is:

- easy to run locally with one command,
- fast to iterate on while the scientific core stays in normal Python modules,
- strong for sliders, selectors, tables, and export buttons,
- good enough for pseudo-live playback using session state and timed reruns,
- simple to extend later with controller diagnostics, tool-calling hooks, or an external agent backend.

The app does **not** rewrite the simulator. It wraps the existing model, optimizer, and controller logic.

## V1/V2 modeling assumptions

This repository is intentionally an MVP. It is designed to be easy to inspect and extend rather than to reproduce a specific plant exactly.

1. **Single mixed reactor:** the secondary treatment system is represented as one equivalent CSTR-like reactor with hydraulic exchange and retained biomass.
2. **Constant influent:** influent NH4, NO2, NO3, COD, and DO are constant within one simulation.
3. **Biomass retention via SRT:** biomass washout is governed by sludge retention time rather than hydraulic retention time.
4. **pH is an input, not a dynamic state:** pH affects kinetics through empirical correction factors and is shown in the UI as a fixed input trace.
5. **Temperature is an input:** temperature affects rates through Arrhenius-style correction factors.
6. **N2O pathways are simplified:** v1 uses lumped surrogate terms for nitrifier denitrification, hydroxylamine-linked production, heterotrophic production, heterotrophic reduction, and stripping.
7. **Aeration energy is a proxy:** energy is not plant electricity; it is an aeration-intensity proxy proportional to oxygen transfer demand.
8. **Live visualization is pseudo-live:** the UI precomputes trajectories, then reveals them progressively using session state and timed reruns.
9. **Agent mode is a placeholder:** the adaptive agent is currently a transparent heuristic that observes states and updates DO target stepwise.
10. **Goal is qualitative reproduction:** the model is tuned to reproduce the *direction* of literature-reported aeration effects, not to serve as a calibrated digital twin.

## Repository layout

```text
n2o-aeration-model/
├─ README.md
├─ requirements.txt
├─ pyproject.toml
├─ main.py
├─ app/
│  └─ streamlit_app.py
├─ configs/
│  ├─ base_case.yaml
│  ├─ low_do.yaml
│  ├─ medium_do.yaml
│  ├─ high_do.yaml
│  └─ dynamic_do.yaml
├─ data/
│  └─ references.md
├─ src/
│  └─ n2o_model/
│     ├─ __init__.py
│     ├─ parameters.py
│     ├─ states.py
│     ├─ kinetics.py
│     ├─ aeration.py
│     ├─ controller.py
│     ├─ process_model.py
│     ├─ simulator.py
│     ├─ scenarios.py
│     ├─ optimizer.py
│     ├─ plotting.py
│     ├─ interactive.py
│     └─ utils.py
├─ scripts/
│  ├─ run_baseline.py
│  ├─ run_scenarios.py
│  ├─ run_optimization.py
│  └─ run_app.py
└─ results/
   └─ .gitkeep
```

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Quick start

Run a single scenario from the CLI:

```bash
python main.py run --config configs/base_case.yaml
```

Compare multiple aeration strategies from the CLI:

```bash
python main.py compare --configs configs/low_do.yaml configs/medium_do.yaml configs/high_do.yaml configs/dynamic_do.yaml
```

Run the simple optimization layer:

```bash
python main.py optimize --config configs/base_case.yaml
```

Run the Streamlit interface:

```bash
streamlit run app/streamlit_app.py
```

or:

```bash
python scripts/run_app.py
```

## What the Streamlit app provides

- sidebar controls for influent, biomass, N2O pathways, aeration/control, and simulation settings
- pseudo-live playback of trajectories with start, pause, and reset
- single-run exploration for fixed, rule-based, optimizer, and mock agent modes
- scenario comparison for low / medium / high / dynamic / optimizer-enabled strategies
- KPI display for N2O emissions, effluent quality, and aeration energy
- current controller decision text and downloadable run data

## Notes on scientific grounding

The repository structure and assumptions are inspired by wastewater N2O literature that emphasizes:

- DO, nitrite, COD/N, pH, and temperature as key N2O drivers
- low DO promoting AOB-related N2O production
- denitrification acting as both an N2O source and sink
- dynamic operational conditions and aeration strategy as important levers for mitigation

See `data/references.md` for the sources used to shape the v1 assumptions.

## Suggested next extensions

- split the equivalent reactor into aerobic + anoxic zones
- calibrate against plant or batch data
- add explicit alkalinity / pH dynamics
- replace the mock adaptive controller with MPC, RL, or an LLM/tool-using controller
- add uncertainty quantification / Monte Carlo analysis
