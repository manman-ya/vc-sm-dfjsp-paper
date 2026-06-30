from __future__ import annotations

import argparse
from pathlib import Path

from mvc_experiment_utils import ROOT, aggregate_mean, read_csv, write_csv
from smdfjsp.metrics.stat_tests import wilcoxon_signed_rank


SYMBOL_ROWS = [
    {"kind": "set", "symbol": "J", "meaning": "Set of jobs/orders", "code_mapping": "instance.jobs"},
    {"kind": "set", "symbol": "V", "meaning": "Set of value chains", "code_mapping": "job.value_chain_id; sru.value_chain_id"},
    {"kind": "set", "symbol": "T", "meaning": "Set of service types", "code_mapping": "job.type_id; sru.service_type_ids"},
    {"kind": "set", "symbol": "U", "meaning": "Set of SRUs", "code_mapping": "instance.srus"},
    {"kind": "set", "symbol": "M_u", "meaning": "Machines in SRU u", "code_mapping": "sru.machine_ids"},
    {"kind": "set", "symbol": "O_j", "meaning": "Operations of job j", "code_mapping": "job.operations"},
    {"kind": "set", "symbol": "A_j", "meaning": "Candidate SRUs of job j", "code_mapping": "build_mvc_compatible_sru_map"},
    {"kind": "parameter", "symbol": "vc_j", "meaning": "Value-chain ownership of job j", "code_mapping": "job.value_chain_id"},
    {"kind": "parameter", "symbol": "type_j", "meaning": "Service type required by job j", "code_mapping": "job.type_id"},
    {"kind": "parameter", "symbol": "vc_u", "meaning": "Value-chain ownership of SRU u", "code_mapping": "sru.value_chain_id"},
    {"kind": "parameter", "symbol": "p_{j,o,u,m}", "meaning": "Processing time", "code_mapping": "option_index[(j,o,u)][m][0]"},
    {"kind": "parameter", "symbol": "c_{j,o,u,m}", "meaning": "Processing cost coefficient", "code_mapping": "option_index[(j,o,u)][m][1]"},
    {"kind": "parameter", "symbol": "tt_{j,u}", "meaning": "Transport time", "code_mapping": "instance.transport_time[(j,u)]"},
    {"kind": "parameter", "symbol": "tc_{j,u}", "meaning": "Transport cost", "code_mapping": "instance.transport_cost[(j,u)]"},
    {"kind": "parameter", "symbol": "fc_{j,u}", "meaning": "Fixed cross-chain collaboration cost", "code_mapping": "instance.cross_chain_fixed_cost[(j,u)]"},
    {"kind": "variable", "symbol": "x_{j,u}", "meaning": "Whether job j is assigned to SRU u", "code_mapping": "UA[j] = u"},
    {"kind": "variable", "symbol": "q_{j,u}", "meaning": "Whether assignment j-u is cross-chain", "code_mapping": "instance.is_cross_chain[(j,u)]"},
]


ALGORITHM_PARAMETER_ROWS = [
    {"parameter": "popsize", "recommended_value": "50-100", "code_default": "MVCEDATSConfig.popsize=50"},
    {"parameter": "max_iter", "recommended_value": "100-200", "code_default": "MVCEDATSConfig.max_iter=100"},
    {"parameter": "time_limit_s", "recommended_value": "600", "code_default": "MVCEDATSConfig.time_limit_s=100"},
    {"parameter": "alpha", "recommended_value": "0.5", "code_default": "MVCEDATSConfig.alpha=0.5"},
    {"parameter": "beta", "recommended_value": "0.5", "code_default": "MVCEDATSConfig.beta=0.5"},
    {"parameter": "gamma", "recommended_value": "0.5", "code_default": "MVCEDATSConfig.gamma=0.5"},
    {"parameter": "mu", "recommended_value": "0.1-0.2", "code_default": "MVCEDATSConfig.mu=0.1"},
    {"parameter": "prior_weight", "recommended_value": "0.25-0.40", "code_default": "MVCEDATSConfig.prior_weight=0.35"},
    {"parameter": "local_search_steps", "recommended_value": "8-20", "code_default": "MVCEDATSConfig.local_search_steps=8"},
    {"parameter": "nd_pool_max", "recommended_value": "300-500", "code_default": "MVCEDATSConfig.nd_pool_max=300"},
]


EXPLANATORY_CASE_ROWS = [
    {
        "solution": "intra_chain_priority",
        "processing_cost": 92.0,
        "transport_cost": 28.0,
        "cross_fixed_cost": 0.0,
        "total_cost": 120.0,
        "makespan": 95.0,
        "interpretation": "Low collaboration cost, but the value-chain-local SRU becomes the schedule bottleneck.",
    },
    {
        "solution": "cross_chain_priority",
        "processing_cost": 98.0,
        "transport_cost": 30.0,
        "cross_fixed_cost": 40.0,
        "total_cost": 168.0,
        "makespan": 68.0,
        "interpretation": "Higher cross-chain cost buys shorter completion time by using external SRU capacity.",
    },
    {
        "solution": "compromise",
        "processing_cost": 95.0,
        "transport_cost": 25.0,
        "cross_fixed_cost": 25.0,
        "total_cost": 145.0,
        "makespan": 78.0,
        "interpretation": "Intermediate assignment balances collaboration cost and makespan.",
    },
]


FIGURE_INVENTORY_ROWS = [
    {
        "figure_id": "Fig. Pareto-Global",
        "file_pattern": "figures/pareto_fronts.png",
        "content": "Overall Pareto points grouped by algorithm and cross-chain mode.",
        "paper_use": "Main comparison overview.",
    },
    {
        "figure_id": "Fig. Pareto-Instance-OnOff",
        "file_pattern": "main_experiment/pareto/combined_front_plots/*_merged_on_off_nondominated_front.png",
        "content": "Per-instance merged on/off all-seed non-dominated front; points are labelled as off only, on only, or off+on.",
        "paper_use": "Instance-level evidence for cross-chain collaboration effects.",
    },
    {
        "figure_id": "Fig. Pareto-Algorithm-Instance",
        "file_pattern": "main_experiment/pareto/algorithm_front_plots/by_instance/*_algorithm_pareto_fronts.png",
        "content": "Per-instance algorithm Pareto-front comparison. Colors represent algorithms; markers represent off/on modes.",
        "paper_use": "Instance-level algorithm comparison.",
    },
    {
        "figure_id": "Fig. HV",
        "file_pattern": "figures/main_hv.png",
        "content": "Normalized hypervolume comparison across algorithms and cross-chain modes.",
        "paper_use": "Main performance comparison.",
    },
    {
        "figure_id": "Fig. Ablation",
        "file_pattern": "figures/ablation_hv.png",
        "content": "Ablation performance comparison for A0-A5 variants.",
        "paper_use": "Component contribution analysis.",
    },
    {
        "figure_id": "Fig. Sensitivity",
        "file_pattern": "figures/sensitivity_cross_ratio.png",
        "content": "Sensitivity of cross-chain ratio under fixed-cost, transport-cost, and time-scale scenarios.",
        "paper_use": "Parameter sensitivity analysis.",
    },
]


def _pairwise_tests(rows: list[dict]) -> list[dict]:
    by_key = {}
    for row in rows:
        key = (row.get("instance", ""), row.get("cross_chain", ""), row.get("seed", ""))
        by_key.setdefault(key, {})[row.get("algorithm", "")] = row
    pairs = [("mvc-edats", "nsgaii"), ("mvc-edats", "moead"), ("moead", "nsgaii")]
    out = []
    for metric, smaller_is_better in [("hv", False), ("igd", True), ("gd", True), ("spacing", True)]:
        for a, b in pairs:
            va = []
            vb = []
            for alg_rows in by_key.values():
                if a in alg_rows and b in alg_rows:
                    va.append(float(alg_rows[a][metric]))
                    vb.append(float(alg_rows[b][metric]))
            if va and vb:
                w_m, p_value, win = wilcoxon_signed_rank(va, vb, smaller_is_better=smaller_is_better)
                out.append({"metric": metric, "algorithm_a": a, "algorithm_b": b, "samples": len(va), "w_m": w_m, "p_value": p_value, "win": win})
    return out


def _neighborhood_summary(rows: list[dict]) -> list[dict]:
    totals: dict[str, dict[str, float]] = {}
    for row in rows:
        for key, value in row.items():
            key = str(key)
            prefix = None
            for candidate in ("nh_generated_", "nh_accepted_", "nh_reward_"):
                if key.startswith(candidate):
                    prefix = candidate
                    break
            if prefix is None:
                continue
            kind = key.replace(prefix, "")
            bucket = totals.setdefault(kind, {"generated": 0.0, "accepted": 0.0, "reward": 0.0})
            metric = prefix.replace("nh_", "").strip("_")
            bucket[metric] += float(value or 0.0)
    out = []
    for kind, values in sorted(totals.items()):
        generated = values.get("generated", 0.0)
        accepted = values.get("accepted", 0.0)
        reward = values.get("reward", 0.0)
        out.append(
            {
                "neighborhood": kind,
                "generated": generated,
                "accepted": accepted,
                "reward": reward,
                "acceptance_rate": accepted / generated if generated > 0 else 0.0,
            }
        )
    return out


def _stop_reason_summary(rows: list[dict]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict[str, object]] = {}
    for row in rows:
        key = (str(row.get("algorithm", "")), str(row.get("cross_chain", "")), str(row.get("stop_reason", "")))
        item = grouped.setdefault(
            key,
            {
                "algorithm": key[0],
                "cross_chain": key[1],
                "stop_reason": key[2],
                "runs": 0,
                "mean_iterations_completed": 0.0,
                "mean_runtime_s": 0.0,
            },
        )
        runs = int(item["runs"]) + 1
        item["mean_iterations_completed"] = (
            (float(item["mean_iterations_completed"]) * (runs - 1)) + float(row.get("iterations_completed", 0.0))
        ) / runs
        item["mean_runtime_s"] = ((float(item["mean_runtime_s"]) * (runs - 1)) + float(row.get("runtime_s", 0.0))) / runs
        item["runs"] = runs
    return list(grouped.values())


def _read_first_existing(*paths: Path) -> list[dict]:
    for path in paths:
        if path.exists():
            return read_csv(path)
    return []


def main() -> None:
    parser = argparse.ArgumentParser(description="Build CSV tables from MVC experiment outputs.")
    parser.add_argument("--experiment-dir", default="reports/mvc_mk01_15_formal_2obj/main_experiment")
    parser.add_argument("--ablation-dir", default="reports/mvc_mk01_15_formal_2obj/ablation")
    parser.add_argument("--sensitivity-dir", default="reports/mvc_mk01_15_formal_2obj/sensitivity")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_2obj/tables")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    exp_dir = ROOT / args.experiment_dir if not Path(args.experiment_dir).is_absolute() else Path(args.experiment_dir)
    abl_dir = ROOT / args.ablation_dir if not Path(args.ablation_dir).is_absolute() else Path(args.ablation_dir)
    sen_dir = ROOT / args.sensitivity_dir if not Path(args.sensitivity_dir).is_absolute() else Path(args.sensitivity_dir)

    exp_metrics = read_csv(exp_dir / "metrics" / "metrics_summary.csv")
    exp_points = read_csv(exp_dir / "pareto" / "all_pareto_points.csv")
    ablation_metrics = _read_first_existing(abl_dir / "all_instance_ablation_summary.csv", abl_dir / "ablation_summary.csv")
    ablation_history = _read_first_existing(abl_dir / "all_instance_ablation_history.csv", abl_dir / "ablation_history.csv")
    sensitivity_selected = _read_first_existing(sen_dir / "all_instance_sensitivity_selected.csv", sen_dir / "sensitivity_selected.csv")

    write_csv(out_dir / "table_symbol_definition.csv", SYMBOL_ROWS)
    write_csv(out_dir / "table_algorithm_parameters.csv", ALGORITHM_PARAMETER_ROWS)
    write_csv(out_dir / "table_explanatory_case.csv", EXPLANATORY_CASE_ROWS)
    write_csv(out_dir / "table_figure_inventory.csv", FIGURE_INVENTORY_ROWS)
    write_csv(
        out_dir / "table_algorithm_performance.csv",
        aggregate_mean(
            exp_metrics,
            ["algorithm", "cross_chain"],
            [
                "hv",
                "igd",
                "raw_igd",
                "gd",
                "spacing",
                "front_size",
                "runtime_s",
                "iterations_completed",
                "algorithm_elapsed_s",
                "mean_total_cost",
                "mean_makespan",
            ],
        ),
    )
    write_csv(
        out_dir / "table_cross_chain_analysis.csv",
        aggregate_mean(
            exp_metrics,
            ["algorithm", "cross_chain"],
            ["min_total_cost", "min_makespan", "mean_cross_chain_ratio", "mean_sru_load_std", "mean_cross_fixed_cost"],
        ),
    )
    write_csv(
        out_dir / "table_ablation.csv",
        aggregate_mean(
            ablation_metrics,
            ["variant_code", "variant", "cross_chain"],
            ["hv", "igd", "raw_igd", "gd", "spacing", "front_size", "runtime_s", "mean_cross_chain_ratio"],
        ),
    )
    write_csv(
        out_dir / "table_cost_breakdown.csv",
        aggregate_mean(
            exp_points,
            ["algorithm", "cross_chain"],
            ["processing_cost", "transport_cost", "cross_fixed_cost", "total_cost"],
        ),
    )
    write_csv(out_dir / "table_neighborhood_contribution.csv", _neighborhood_summary(ablation_history))
    write_csv(out_dir / "table_stop_reasons.csv", _stop_reason_summary(exp_metrics))
    write_csv(out_dir / "sensitivity_selected.csv", sensitivity_selected)
    write_csv(out_dir / "statistical_tests.csv", _pairwise_tests(exp_metrics))
    print(f"tables_dir: {out_dir.as_posix()}")


if __name__ == "__main__":
    main()
