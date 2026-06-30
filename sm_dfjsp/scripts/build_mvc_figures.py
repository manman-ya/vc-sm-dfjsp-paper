from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_mvc_algorithm_fronts import build_algorithm_fronts
from build_mvc_instance_nd_fronts import build_instance_nd_fronts
from mvc_experiment_utils import ROOT, read_csv
from smdfjsp.visualization.mvc_plots import (
    plot_cross_chain_flow,
    plot_algorithm_flow,
    plot_explanatory_case,
    plot_history_lines,
    plot_metric_bars,
    plot_neighborhood_contribution,
    plot_pareto_csv,
    plot_problem_structure,
    plot_sru_loads,
)


def _read_first_existing(*paths: Path) -> list[dict]:
    for path in paths:
        if path.exists():
            return read_csv(path)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MVC experiment figures.")
    parser.add_argument("--experiment-dir", default="reports/mvc_mk01_15_formal_2obj/main_experiment")
    parser.add_argument("--ablation-dir", default="reports/mvc_mk01_15_formal_2obj/ablation")
    parser.add_argument("--sensitivity-dir", default="reports/mvc_mk01_15_formal_2obj/sensitivity")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_2obj/figures")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    exp_dir = ROOT / args.experiment_dir if not Path(args.experiment_dir).is_absolute() else Path(args.experiment_dir)
    abl_dir = ROOT / args.ablation_dir if not Path(args.ablation_dir).is_absolute() else Path(args.ablation_dir)
    sen_dir = ROOT / args.sensitivity_dir if not Path(args.sensitivity_dir).is_absolute() else Path(args.sensitivity_dir)

    pareto_rows = read_csv(exp_dir / "pareto" / "all_pareto_points.csv")
    metric_rows = read_csv(exp_dir / "metrics" / "metrics_summary.csv")
    ablation_rows = _read_first_existing(abl_dir / "all_instance_ablation_summary.csv", abl_dir / "ablation_summary.csv")
    ablation_history = _read_first_existing(abl_dir / "all_instance_ablation_history.csv", abl_dir / "ablation_history.csv")
    sensitivity_rows = _read_first_existing(sen_dir / "all_instance_sensitivity_selected.csv", sen_dir / "sensitivity_selected.csv")
    history_rows = []
    for path in sorted((exp_dir / "raw").glob("*_history.csv")):
        history_rows.extend(read_csv(path))
    for row in metric_rows:
        row["label"] = f"{row.get('algorithm', '')}-{row.get('cross_chain', '')}"
    for row in ablation_rows:
        row["label"] = f"{row.get('algorithm', '')}-{row.get('cross_chain', '')}-{row.get('seed', '')}"
    for row in sensitivity_rows:
        row["label"] = (
            f"cf{row.get('fixed_cost', '')}/tc{row.get('transport_scale', '')}/"
            f"xt{row.get('cross_time_scale', '')}/{row.get('cross_chain', '')}"
        )
    plot_problem_structure(out_dir / "problem_structure.png")
    plot_algorithm_flow(out_dir / "mvc_edats_flow.png")
    plot_explanatory_case(out_dir / "explanatory_small_case.png")
    plot_pareto_csv(pareto_rows, out_dir / "pareto_fronts.png", "MVC-SM-DFJSP Pareto Fronts")
    build_instance_nd_fronts(exp_dir, out_dir / "per_instance_nd")
    build_algorithm_fronts(exp_dir, out_dir / "algorithm_pareto_by_instance")
    plot_metric_bars(metric_rows, out_dir / "main_hv.png", "hv", "Main Experiment Normalized HV")
    plot_metric_bars(ablation_rows, out_dir / "ablation_hv.png", "hv", "Ablation Normalized HV")
    plot_metric_bars(sensitivity_rows, out_dir / "sensitivity_cross_ratio.png", "cross_chain_ratio", "Sensitivity Cross-Chain Ratio")
    plot_history_lines(
        history_rows or ablation_history,
        out_dir / "convergence_curves.png",
        "best_cost",
        "Mean Best-Cost Convergence",
    )
    plot_history_lines(
        history_rows or ablation_history,
        out_dir / "convergence_makespan.png",
        "best_makespan",
        "Mean Best-Makespan Convergence",
    )
    plot_neighborhood_contribution(ablation_history or history_rows, out_dir / "neighborhood_contribution.png")

    flow = {}
    loads = {}
    for row in pareto_rows:
        try:
            for key, value in json.loads(str(row.get("cross_chain_flow", "{}"))).items():
                flow[key] = flow.get(key, 0.0) + float(value)
        except json.JSONDecodeError:
            pass
        try:
            for key, value in json.loads(str(row.get("sru_loads", "{}"))).items():
                loads[key] = loads.get(key, 0.0) + float(value)
        except json.JSONDecodeError:
            pass
    plot_cross_chain_flow(flow, out_dir / "cross_chain_flow.png")
    plot_sru_loads(loads, out_dir / "sru_load_distribution.png", "SRU Load Distribution")
    print(f"figures_dir: {out_dir.as_posix()}")


if __name__ == "__main__":
    main()
