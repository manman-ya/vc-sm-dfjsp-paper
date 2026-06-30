from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, stdev
from typing import Mapping, Sequence

import matplotlib.pyplot as plt

from mvc_experiment_utils import ROOT, read_csv, write_csv
from smdfjsp.metrics.stat_tests import wilcoxon_signed_rank


METRICS = {
    "hv": "higher",
    "igd": "lower",
    "raw_igd": "lower",
    "min_total_cost": "lower",
    "min_makespan": "lower",
    "runtime_s": "lower",
    "algorithm_elapsed_s": "lower",
    "budget_elapsed_s": "lower",
    "evaluations_completed": "lower",
}
CONVERGENCE_METRICS = ("best_cost", "best_makespan")
T_975 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365,
    8: 2.306, 9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145,
    15: 2.131, 16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086,
    21: 2.080, 22: 2.074, 23: 2.069, 24: 2.064, 25: 2.060, 26: 2.056,
    27: 2.052, 28: 2.048, 29: 2.045, 30: 2.042,
}


def _resolve(path: str | Path) -> Path:
    value = Path(path)
    return value if value.is_absolute() else ROOT / value


def _number(value: object) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _summary(values: Sequence[float]) -> dict[str, float | int]:
    n = len(values)
    avg = mean(values)
    sd = stdev(values) if n > 1 else 0.0
    critical = T_975.get(n - 1, 1.96)
    half_width = critical * sd / math.sqrt(n) if n > 1 else 0.0
    return {
        "n": n,
        "mean": avg,
        "std": sd,
        "ci95_lower": avg - half_width,
        "ci95_upper": avg + half_width,
        "ci95_half_width": half_width,
    }


def _per_instance_statistics(suites: Mapping[str, Path]) -> list[dict]:
    output: list[dict] = []
    for suite, directory in suites.items():
        rows = read_csv(directory / "metrics" / "metrics_summary.csv")
        grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
        for row in rows:
            grouped[(str(row.get("instance", "")), str(row.get("algorithm", "")), str(row.get("cross_chain", "")))].append(row)
        for (instance, algorithm, cross_chain), group in sorted(grouped.items()):
            item: dict[str, object] = {
                "suite": suite,
                "instance": instance,
                "algorithm": algorithm,
                "cross_chain": cross_chain,
                "seeds": len({str(row.get("seed", "")) for row in group}),
            }
            for metric in METRICS:
                values = [_number(row.get(metric)) for row in group]
                finite = [value for value in values if value is not None]
                if not finite:
                    continue
                for suffix, value in _summary(finite).items():
                    item[f"{metric}_{suffix}"] = value
            output.append(item)
    return output


def _holm(rows: list[dict], family_columns: Sequence[str], alpha: float) -> None:
    families: dict[tuple[str, ...], list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        families[tuple(str(row.get(column, "")) for column in family_columns)].append(index)
    for indices in families.values():
        ordered = sorted(indices, key=lambda index: float(rows[index]["p_value"]))
        running = 0.0
        count = len(ordered)
        for rank, index in enumerate(ordered):
            adjusted = min(1.0, (count - rank) * float(rows[index]["p_value"]))
            running = max(running, adjusted)
            rows[index]["holm_adjusted_p"] = running
            rows[index]["significant"] = running < alpha


def _paired_effect(a: Sequence[float], b: Sequence[float], higher_is_better: bool) -> dict[str, float | int]:
    signed = [(x - y) if higher_is_better else (y - x) for x, y in zip(a, b)]
    nonzero = [value for value in signed if value != 0.0]
    wins = sum(value > 0.0 for value in signed)
    losses = sum(value < 0.0 for value in signed)
    ties = len(signed) - wins - losses
    order = sorted(range(len(nonzero)), key=lambda index: abs(nonzero[index]))
    ranks = [0.0] * len(nonzero)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and abs(nonzero[order[end]]) == abs(nonzero[order[start]]):
            end += 1
        average_rank = (start + 1 + end) / 2.0
        for position in range(start, end):
            ranks[order[position]] = average_rank
        start = end
    positive_ranks = sum(rank for rank, value in zip(ranks, nonzero) if value > 0.0)
    negative_ranks = sum(rank for rank, value in zip(ranks, nonzero) if value < 0.0)
    rank_total = positive_ranks + negative_ranks
    rank_biserial = (positive_ranks - negative_ranks) / rank_total if rank_total else 0.0
    return {
        "mean_full_minus_variant": mean(x - y for x, y in zip(a, b)),
        "median_full_minus_variant": median(x - y for x, y in zip(a, b)),
        "full_wins": wins,
        "full_losses": losses,
        "ties": ties,
        "rank_biserial": rank_biserial,
    }


def _ablation_tests(ablation_dir: Path, alpha: float) -> list[dict]:
    rows = read_csv(ablation_dir / "all_instance_ablation_summary.csv")
    indexed = {
        (str(row.get("instance", "")), str(row.get("seed", "")), str(row.get("variant_code", ""))): row
        for row in rows
    }
    variants = sorted({str(row.get("variant_code", "")) for row in rows if str(row.get("variant_code", "")) != "A0"})
    instances = sorted({str(row.get("instance", "")) for row in rows})
    tests: list[dict] = []
    for scope, scope_instances in [("overall", instances), *[("instance", [instance]) for instance in instances]]:
        scope_name = "all" if scope == "overall" else scope_instances[0]
        for metric, direction in METRICS.items():
            if metric == "raw_igd":
                continue
            for variant in variants:
                sample_a: list[float] = []
                sample_b: list[float] = []
                pair_ids: list[str] = []
                for instance in scope_instances:
                    seeds = sorted({key[1] for key in indexed if key[0] == instance})
                    for seed in seeds:
                        full = indexed.get((instance, seed, "A0"))
                        reduced = indexed.get((instance, seed, variant))
                        if full is None or reduced is None:
                            continue
                        value_a = _number(full.get(metric))
                        value_b = _number(reduced.get(metric))
                        if value_a is None or value_b is None:
                            continue
                        sample_a.append(value_a)
                        sample_b.append(value_b)
                        pair_ids.append(f"{instance}:seed{seed}")
                if len(sample_a) < 2:
                    continue
                statistic, p_value, _ = wilcoxon_signed_rank(
                    sample_a,
                    sample_b,
                    alpha=alpha,
                    smaller_is_better=direction == "lower",
                )
                test: dict[str, object] = {
                    "scope": scope,
                    "scope_name": scope_name,
                    "metric": metric,
                    "direction": direction,
                    "full_variant": "A0",
                    "compared_variant": variant,
                    "pairs": len(sample_a),
                    "mean_full": mean(sample_a),
                    "mean_variant": mean(sample_b),
                    "wilcoxon_W": statistic,
                    "p_value": p_value,
                    "pair_ids": ";".join(pair_ids),
                }
                test.update(_paired_effect(sample_a, sample_b, direction == "higher"))
                tests.append(test)
    _holm(tests, ("scope", "scope_name", "metric"), alpha)
    return tests


def _load_histories(directory: Path) -> list[list[dict]]:
    histories: list[list[dict]] = []
    for path in sorted((directory / "raw").glob("*_history.csv")):
        rows = read_csv(path)
        if rows:
            histories.append(rows)
    return histories


def _suite_budget(directory: Path, suite: str) -> tuple[str, float]:
    metadata = json.loads((directory / "run_meta.json").read_text(encoding="utf-8"))
    if suite == "equal_cpu_time":
        return "elapsed_s", float(metadata["time_limit"])
    if suite == "equal_evaluations":
        return "evaluations", float(metadata["max_evaluations"])
    return "iter", float(metadata["max_iter"])


def _axis_value(row: Mapping[str, object], axis: str) -> float:
    if axis == "evaluations":
        return float(row.get("evaluations", row.get("evaluation_count", 0.0)))
    return float(row.get(axis, 0.0))


def _convergence(suites: Mapping[str, Path], grid_size: int = 51) -> tuple[list[dict], list[dict]]:
    instance_output: list[dict] = []
    normalized_output: list[dict] = []
    for suite, directory in suites.items():
        histories = _load_histories(directory)
        if not histories:
            continue
        axis, budget = _suite_budget(directory, suite)
        bounds: dict[tuple[str, str], tuple[float, float]] = {}
        for metric in CONVERGENCE_METRICS:
            for instance in {str(history[0].get("instance", "")) for history in histories}:
                values = [
                    float(row[metric])
                    for history in histories
                    if str(history[0].get("instance", "")) == instance
                    for row in history
                    if _number(row.get(metric)) is not None
                ]
                if values:
                    bounds[(instance, metric)] = (min(values), max(values))

        sampled: dict[tuple[str, str, str, str, int], list[float]] = defaultdict(list)
        sampled_normalized: dict[tuple[str, str, str, int], list[float]] = defaultdict(list)
        for history in histories:
            metadata = history[0]
            instance = str(metadata.get("instance", ""))
            algorithm = str(metadata.get("algorithm", ""))
            cross_chain = str(metadata.get("cross_chain", ""))
            ordered = sorted(history, key=lambda row: _axis_value(row, axis))
            for metric in CONVERGENCE_METRICS:
                valid = [row for row in ordered if _number(row.get(metric)) is not None]
                if not valid:
                    continue
                pointer = 0
                for grid_index in range(grid_size):
                    target = budget * grid_index / (grid_size - 1)
                    while pointer + 1 < len(valid) and _axis_value(valid[pointer + 1], axis) <= target:
                        pointer += 1
                    value = float(valid[pointer][metric])
                    sampled[(instance, algorithm, cross_chain, metric, grid_index)].append(value)
                    lower, upper = bounds[(instance, metric)]
                    normalized = (value - lower) / max(upper - lower, 1e-12)
                    sampled_normalized[(algorithm, cross_chain, metric, grid_index)].append(normalized)

        for (instance, algorithm, cross_chain, metric, grid_index), values in sorted(sampled.items()):
            item = {
                "suite": suite,
                "instance": instance,
                "algorithm": algorithm,
                "cross_chain": cross_chain,
                "metric": metric,
                "progress_fraction": grid_index / (grid_size - 1),
                "axis": axis,
                "axis_value": budget * grid_index / (grid_size - 1),
            }
            item.update(_summary(values))
            instance_output.append(item)
        for (algorithm, cross_chain, metric, grid_index), values in sorted(sampled_normalized.items()):
            item = {
                "suite": suite,
                "algorithm": algorithm,
                "cross_chain": cross_chain,
                "metric": metric,
                "progress_fraction": grid_index / (grid_size - 1),
                "normalized_value": "instance-wise observed range; lower is better",
            }
            item.update(_summary(values))
            normalized_output.append(item)
    return instance_output, normalized_output


def _plot_convergence(rows: Sequence[Mapping[str, object]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    suites = sorted({str(row["suite"]) for row in rows})
    for suite in suites:
        figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), constrained_layout=True)
        for axis_plot, metric in zip(axes, CONVERGENCE_METRICS):
            subset = [row for row in rows if row["suite"] == suite and row["metric"] == metric]
            groups: dict[tuple[str, str], list[Mapping[str, object]]] = defaultdict(list)
            for row in subset:
                groups[(str(row["algorithm"]), str(row["cross_chain"]))].append(row)
            for (algorithm, cross_chain), group in sorted(groups.items()):
                ordered = sorted(group, key=lambda row: float(row["progress_fraction"]))
                x = [float(row["progress_fraction"]) for row in ordered]
                y = [float(row["mean"]) for row in ordered]
                low = [float(row["ci95_lower"]) for row in ordered]
                high = [float(row["ci95_upper"]) for row in ordered]
                label = f"{algorithm}-{cross_chain}"
                axis_plot.plot(x, y, linewidth=1.5, label=label)
                axis_plot.fill_between(x, low, high, alpha=0.10)
            axis_plot.set_title(metric.replace("_", " ").title())
            axis_plot.set_xlabel("Budget fraction")
            axis_plot.set_ylabel("Normalized incumbent (lower is better)")
            axis_plot.grid(alpha=0.25)
        axes[1].legend(fontsize=7, ncol=2)
        figure.savefig(out_dir / f"convergence_{suite}.png", dpi=240)
        figure.savefig(out_dir / f"convergence_{suite}.pdf")
        plt.close(figure)


def _module_runtime(suites: Mapping[str, Path], ablation_dir: Path) -> list[dict]:
    output: list[dict] = []
    sources = [(suite, read_csv(directory / "raw" / "runtime_summary.csv")) for suite, directory in suites.items()]
    sources.append(("ablation", read_csv(ablation_dir / "all_instance_ablation_summary.csv")))
    for suite, rows in sources:
        grouped: dict[tuple[str, str, str, str, str], list[float]] = defaultdict(list)
        for row in rows:
            for column, raw_value in row.items():
                if not column.startswith("module_") or not column.endswith("_s"):
                    continue
                value = _number(raw_value)
                if value is None:
                    continue
                grouped[
                    (
                        str(row.get("algorithm", "")),
                        str(row.get("cross_chain", "")),
                        str(row.get("variant_code", "")),
                        str(row.get("time_measure", "wall")),
                        column.removeprefix("module_").removesuffix("_s"),
                    )
                ].append(value)
        for (algorithm, cross_chain, variant, time_measure, module), values in sorted(grouped.items()):
            item = {
                "suite": suite,
                "algorithm": algorithm,
                "cross_chain": cross_chain,
                "variant_code": variant,
                "time_measure": time_measure,
                "module": module,
            }
            item.update(_summary(values))
            output.append(item)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze rigorous 20-seed MVC experiments.")
    parser.add_argument("--fixed-dir", required=True)
    parser.add_argument("--equal-time-dir", required=True)
    parser.add_argument("--equal-fe-dir", required=True)
    parser.add_argument("--ablation-dir", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()

    suites = {
        "fixed_iteration": _resolve(args.fixed_dir),
        "equal_cpu_time": _resolve(args.equal_time_dir),
        "equal_evaluations": _resolve(args.equal_fe_dir),
    }
    ablation_dir = _resolve(args.ablation_dir)
    out_dir = _resolve(args.out_dir)

    write_csv(out_dir / "per_instance_mean_std_ci95.csv", _per_instance_statistics(suites))
    write_csv(out_dir / "ablation_paired_wilcoxon_holm.csv", _ablation_tests(ablation_dir, args.alpha))
    by_instance, normalized = _convergence(suites)
    write_csv(out_dir / "convergence_by_instance.csv", by_instance)
    write_csv(out_dir / "convergence_normalized_aggregate.csv", normalized)
    _plot_convergence(normalized, out_dir / "figures")
    write_csv(out_dir / "module_runtime_mean_std_ci95.csv", _module_runtime(suites, ablation_dir))
    print(f"analysis_dir: {out_dir.as_posix()}")


if __name__ == "__main__":
    main()
