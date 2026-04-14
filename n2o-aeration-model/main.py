"""CLI entrypoint for the N2O aeration model repository."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from n2o_model.optimizer import optimize_fixed_do_setpoints
from n2o_model.plotting import plot_scenario_comparison, plot_timeseries_bundle
from n2o_model.scenarios import load_config
from n2o_model.simulator import summarize_results, run_simulation
from n2o_model.utils import ensure_dir


def _cmd_run(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    results = run_simulation(cfg)
    plot_timeseries_bundle(results, cfg.output_dir)
    summary = summarize_results(results)
    print(summary.to_string(index=False))
    print(f"Saved results to: {cfg.output_dir}")


def _cmd_compare(args: argparse.Namespace) -> None:
    runs = []
    for config_path in args.configs:
        cfg = load_config(config_path)
        results = run_simulation(cfg)
        plot_timeseries_bundle(results, cfg.output_dir)
        runs.append((cfg.scenario_name, results))
    out_dir = ensure_dir(args.output_dir or "results/comparison")
    plot_scenario_comparison(runs, out_dir)
    print(f"Saved comparison plots to: {out_dir}")
    for _, results in runs:
        print(summarize_results(results).to_string(index=False))


def _cmd_optimize(args: argparse.Namespace) -> None:
    cfg = load_config(args.config)
    opt_result = optimize_fixed_do_setpoints(cfg)
    print("Optimization ranking:")
    print(opt_result.candidate_table.to_string(index=False))
    plot_timeseries_bundle(opt_result.best_results, opt_result.best_config.output_dir)
    print(f"Best scenario: {opt_result.best_config.scenario_name}")
    print(f"Saved best-run plots to: {opt_result.best_config.output_dir}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="N2O aeration model")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run one scenario")
    run_parser.add_argument("--config", required=True, help="Path to YAML config")
    run_parser.set_defaults(func=_cmd_run)

    compare_parser = subparsers.add_parser("compare", help="Run and compare multiple scenarios")
    compare_parser.add_argument("--configs", nargs="+", required=True, help="List of YAML config files")
    compare_parser.add_argument("--output-dir", default="results/comparison", help="Where comparison plots go")
    compare_parser.set_defaults(func=_cmd_compare)

    optimize_parser = subparsers.add_parser("optimize", help="Grid-search fixed DO setpoints")
    optimize_parser.add_argument("--config", required=True, help="Base YAML config")
    optimize_parser.set_defaults(func=_cmd_optimize)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
