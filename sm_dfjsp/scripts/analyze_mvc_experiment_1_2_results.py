from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _read_csv(path: Path) -> list[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(str(key))
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _float(value: object, default: float = math.nan) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _fmt(value: object, digits: int = 4) -> str:
    number = _float(value)
    if math.isnan(number):
        return ""
    return f"{number:.{digits}f}"


def _group(rows: Iterable[Mapping[str, object]], keys: Sequence[str]) -> dict[tuple[str, ...], list[Mapping[str, object]]]:
    grouped: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(str(row.get(k, "")) for k in keys)].append(row)
    return grouped


def _aggregate_metrics(metrics: Sequence[Mapping[str, object]], keys: Sequence[str]) -> list[dict]:
    metric_cols = [
        "hv",
        "igd",
        "raw_igd",
        "gd",
        "spacing",
        "front_size",
        "runtime_s",
        "iterations_completed",
        "min_total_cost",
        "min_makespan",
        "mean_total_cost",
        "mean_makespan",
        "mean_cross_chain_ratio",
        "mean_cross_fixed_cost",
        "mean_transport_cost",
        "mean_sru_load_std",
    ]
    out: list[dict] = []
    for key, group in sorted(_group(metrics, keys).items()):
        row = {col: key[idx] for idx, col in enumerate(keys)}
        row["runs"] = len(group)
        for col in metric_cols:
            values = [_float(item.get(col)) for item in group]
            values = [v for v in values if not math.isnan(v)]
            if values:
                row[f"mean_{col}"] = mean(values)
                row[f"best_{col}"] = max(values) if col == "hv" else min(values)
        out.append(row)
    return out


def _rank_winners(rows: Sequence[Mapping[str, object]], metric: str, larger_better: bool) -> dict[str, int]:
    winners: dict[str, int] = defaultdict(int)
    for _, group in _group(rows, ["instance"]).items():
        candidates = []
        for row in group:
            value = _float(row.get(metric))
            if not math.isnan(value):
                candidates.append((str(row.get("algorithm", "")), value))
        if not candidates:
            continue
        best_value = max(v for _, v in candidates) if larger_better else min(v for _, v in candidates)
        for algorithm, value in candidates:
            if abs(value - best_value) <= 1e-9:
                winners[algorithm] += 1
    return dict(sorted(winners.items()))


def _aggregate_by_instance_algorithm(metrics: Sequence[Mapping[str, object]]) -> list[dict]:
    return _aggregate_metrics(metrics, ["instance", "algorithm", "cross_chain"])


def _mechanism_rows(instance_algorithm_rows: Sequence[Mapping[str, object]]) -> list[dict]:
    by_key = {
        (str(row.get("instance", "")), str(row.get("algorithm", "")), str(row.get("cross_chain", ""))): row
        for row in instance_algorithm_rows
    }
    out: list[dict] = []
    instances = sorted({key[0] for key in by_key})
    for instance in instances:
        off = by_key.get((instance, "mvc-edats", "off"))
        on = by_key.get((instance, "mvc-edats", "on"))
        if off is None or on is None:
            continue
        off_makespan = _float(off.get("mean_min_makespan"))
        on_makespan = _float(on.get("mean_min_makespan"))
        off_cost = _float(off.get("mean_min_total_cost"))
        on_cost = _float(on.get("mean_min_total_cost"))
        off_load = _float(off.get("mean_mean_sru_load_std"))
        on_load = _float(on.get("mean_mean_sru_load_std"))
        out.append(
            {
                "instance": instance,
                "off_min_makespan": off_makespan,
                "on_min_makespan": on_makespan,
                "makespan_delta_on_minus_off": on_makespan - off_makespan,
                "makespan_improvement_pct": (off_makespan - on_makespan) / off_makespan * 100.0 if off_makespan > 0 else "",
                "off_min_total_cost": off_cost,
                "on_min_total_cost": on_cost,
                "cost_delta_on_minus_off": on_cost - off_cost,
                "cost_increase_pct": (on_cost - off_cost) / off_cost * 100.0 if off_cost > 0 else "",
                "off_sru_load_std": off_load,
                "on_sru_load_std": on_load,
                "sru_load_std_delta_on_minus_off": on_load - off_load,
                "on_cross_chain_ratio": _float(on.get("mean_mean_cross_chain_ratio")),
                "on_cross_fixed_cost": _float(on.get("mean_mean_cross_fixed_cost")),
            }
        )
    return out


def _significant_rows(rows: Sequence[Mapping[str, object]]) -> list[Mapping[str, object]]:
    out = []
    for row in rows:
        significant = str(row.get("significant", "")).lower() == "true"
        if significant:
            out.append(row)
    return out


def _table(rows: Sequence[Mapping[str, object]], columns: Sequence[str], max_rows: int | None = None) -> list[str]:
    use_rows = list(rows[:max_rows] if max_rows else rows)
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in use_rows:
        values = []
        for col in columns:
            value = row.get(col, "")
            if isinstance(value, float):
                values.append(_fmt(value))
            else:
                values.append(str(value))
        lines.append("| " + " | ".join(values) + " |")
    return lines


def build_report(report_root: Path, out_dir: Path) -> Path:
    metrics = _read_csv(report_root / "combined_experiment_1_2" / "metrics" / "metrics_summary.csv")
    pareto = _read_csv(report_root / "combined_experiment_1_2" / "pareto" / "all_pareto_points.csv")
    runtime = _read_csv(report_root / "combined_experiment_1_2" / "raw" / "runtime_summary.csv")
    validation = _read_csv(report_root / "validation" / "validation_summary.csv")
    wilcoxon_hv_igd = _read_csv(report_root / "stat_tests" / "wilcoxon_hv_igd.csv")
    wilcoxon_cost_makespan = _read_csv(report_root / "stat_tests" / "wilcoxon_cost_makespan.csv")
    friedman = _read_csv(report_root / "stat_tests" / "friedman_ranking.csv")
    onoff_summary = _read_csv(
        report_root / "combined_experiment_1_2" / "pareto" / "combined_front_plots" / "merged_on_off_nondominated_front_summary.csv"
    )
    algorithm_front_summary = _read_csv(
        report_root / "combined_experiment_1_2" / "pareto" / "algorithm_front_plots" / "algorithm_pareto_front_summary.csv"
    )

    if not metrics:
        raise FileNotFoundError(f"No metrics found under {report_root / 'combined_experiment_1_2' / 'metrics'}")

    by_algorithm_mode = _aggregate_metrics(metrics, ["algorithm", "cross_chain"])
    by_instance_algorithm = _aggregate_by_instance_algorithm(metrics)
    mechanism = _mechanism_rows(by_instance_algorithm)
    algorithm_off = [r for r in by_instance_algorithm if str(r.get("cross_chain", "")) == "off"]
    exp1_winners = {
        "hv": _rank_winners(algorithm_off, "mean_hv", True),
        "igd": _rank_winners(algorithm_off, "mean_igd", False),
        "min_makespan": _rank_winners(algorithm_off, "mean_min_makespan", False),
        "min_total_cost": _rank_winners(algorithm_off, "mean_min_total_cost", False),
    }

    _write_csv(out_dir / "summary_by_algorithm_mode.csv", by_algorithm_mode)
    _write_csv(out_dir / "summary_by_instance_algorithm_mode.csv", by_instance_algorithm)
    _write_csv(out_dir / "mechanism_mvc_edats_on_off.csv", mechanism)

    total_expected = 375
    completed_runs = len(runtime)
    validation_passed = sum(1 for row in validation if str(row.get("valid", "")).lower() == "true")
    mechanism_count = len(mechanism)
    makespan_better = sum(1 for row in mechanism if _float(row.get("makespan_delta_on_minus_off")) < -1e-9)
    cost_higher = sum(1 for row in mechanism if _float(row.get("cost_delta_on_minus_off")) > 1e-9)
    load_better = sum(1 for row in mechanism if _float(row.get("sru_load_std_delta_on_minus_off")) < -1e-9)
    mean_makespan_improvement = mean(
        [_float(row.get("makespan_improvement_pct")) for row in mechanism if not math.isnan(_float(row.get("makespan_improvement_pct")))]
    ) if mechanism else math.nan
    mean_cost_increase = mean(
        [_float(row.get("cost_increase_pct")) for row in mechanism if not math.isnan(_float(row.get("cost_increase_pct")))]
    ) if mechanism else math.nan
    mean_cross_ratio_on = mean(
        [_float(row.get("on_cross_chain_ratio")) for row in mechanism if not math.isnan(_float(row.get("on_cross_chain_ratio")))]
    ) if mechanism else math.nan

    lines = [
        "# MVC-SM-DFJSP Experiment 1-2 Result Analysis",
        "",
        f"Report root: `{report_root.as_posix()}`",
        "",
        "## 1. Completion Check",
        "",
        f"- Validation passed instances: {validation_passed}/{len(validation)}.",
        f"- Runtime rows: {completed_runs}. Expected formal runs: {total_expected}.",
        f"- Pareto points: {len(pareto)}.",
        f"- Metric rows: {len(metrics)}.",
        f"- On/off merged front summary rows: {len(onoff_summary)}.",
        f"- Algorithm front summary rows: {len(algorithm_front_summary)}.",
        "",
        "## 2. Experiment 1: Off-Mode Algorithm Comparison",
        "",
        "Mean values are averaged over instance-seed metric rows. HV and IGD are normalized per their documented shared bounds; raw_hv and raw_igd retain original objective-space values for audit only. HV is larger-better; IGD, GD, spacing, cost and makespan are smaller-better.",
        "",
        *_table(
            [row for row in by_algorithm_mode if str(row.get("cross_chain", "")) == "off"],
            [
                "algorithm",
                "cross_chain",
                "runs",
                "mean_hv",
                "mean_igd",
                "mean_min_total_cost",
                "mean_min_makespan",
                "mean_runtime_s",
            ],
        ),
        "",
        "Per-instance winner counts after averaging seeds:",
        "",
        f"- HV winners: {exp1_winners['hv']}",
        f"- IGD winners: {exp1_winners['igd']}",
        f"- min makespan winners: {exp1_winners['min_makespan']}",
        f"- min total cost winners: {exp1_winners['min_total_cost']}",
        "",
        "## 3. Experiment 2: MVC-EDA-TS Cross-Chain Mechanism",
        "",
        f"- Instances compared: {mechanism_count}.",
        f"- Cross-on improves min makespan on {makespan_better}/{mechanism_count} instances.",
        f"- Cross-on increases min total cost on {cost_higher}/{mechanism_count} instances.",
        f"- Cross-on reduces SRU load standard deviation on {load_better}/{mechanism_count} instances.",
        f"- Mean makespan improvement: {_fmt(mean_makespan_improvement, 2)}%.",
        f"- Mean min-cost increase: {_fmt(mean_cost_increase, 2)}%.",
        f"- Mean cross-chain ratio under MVC-EDA-TS-on: {_fmt(mean_cross_ratio_on, 4)}.",
        "",
        *_table(
            mechanism,
            [
                "instance",
                "makespan_delta_on_minus_off",
                "makespan_improvement_pct",
                "cost_delta_on_minus_off",
                "cost_increase_pct",
                "on_cross_chain_ratio",
                "sru_load_std_delta_on_minus_off",
            ],
        ),
        "",
        "## 4. Statistical Tests",
        "",
        "Significant Wilcoxon tests after Holm correction:",
        "",
        *_table(
            _significant_rows([*wilcoxon_hv_igd, *wilcoxon_cost_makespan]),
            ["family", "metric", "comparison", "samples", "mean_A", "mean_B", "adjusted_p", "better"],
        ),
        "",
        "Friedman rankings:",
        "",
        *_table(friedman, ["metric", "algorithm_label", "average_rank", "p_value", "significant"]),
        "",
        "## 5. Recommended Interpretation",
        "",
        "- Use Experiment 1 to discuss algorithmic performance only under cross-off. This avoids mixing baseline algorithm ability with cross-chain mechanism effects.",
        "- Use Experiment 2 to discuss the value of cross-chain collaboration within MVC-EDA-TS only.",
        "- If cross-on mainly improves makespan while increasing cost, write it as a cost-time trade-off rather than a universal dominance claim.",
        "- If cross-chain ratio is low in several instances, explain that equal-processing instances provide limited intrinsic incentive for cross-chain use; the newly generated 3.1 mechanism instances can be used as a focused mechanism case study.",
        "",
    ]

    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "experiment_1_2_analysis.md"
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze formal MVC Experiment 1-2 results.")
    parser.add_argument("--report-root", default="reports/mvc_experiment_1_2_formal_80pop_150iter")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()

    report_root = _resolve(args.report_root)
    out_dir = _resolve(args.out_dir) if args.out_dir else report_root / "analysis"
    report_path = build_report(report_root, out_dir)
    print(f"analysis_report: {report_path.as_posix()}")
    print(f"analysis_dir: {out_dir.as_posix()}")


if __name__ == "__main__":
    main()
