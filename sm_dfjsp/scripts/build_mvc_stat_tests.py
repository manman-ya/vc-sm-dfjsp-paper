from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mvc_experiment_utils import read_csv, summarize_metrics, write_csv
from smdfjsp.metrics.stat_tests import wilcoxon_signed_rank


def _rankdata(values: Sequence[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda idx: values[idx])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for pos in range(i, j):
            ranks[order[pos]] = avg_rank
        i = j
    return ranks


def _gamma_q(a: float, x: float) -> float:
    """Regularized upper incomplete gamma Q(a, x), adapted for chi-square survival."""
    if x < 0.0 or a <= 0.0:
        return math.nan
    if x == 0.0:
        return 1.0
    eps = 3.0e-14
    fpmin = 1.0e-300
    gln = math.lgamma(a)

    if x < a + 1.0:
        ap = a
        total = 1.0 / a
        delta = total
        for _ in range(10000):
            ap += 1.0
            delta *= x / ap
            total += delta
            if abs(delta) < abs(total) * eps:
                p = total * math.exp(-x + a * math.log(x) - gln)
                return max(0.0, min(1.0, 1.0 - p))
        p = total * math.exp(-x + a * math.log(x) - gln)
        return max(0.0, min(1.0, 1.0 - p))

    b = x + 1.0 - a
    c = 1.0 / fpmin
    d = 1.0 / max(b, fpmin)
    h = d
    for i in range(1, 10000):
        an = -float(i) * (float(i) - a)
        b += 2.0
        d = an * d + b
        if abs(d) < fpmin:
            d = fpmin
        c = b + an / c
        if abs(c) < fpmin:
            c = fpmin
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            q = math.exp(-x + a * math.log(x) - gln) * h
            return max(0.0, min(1.0, q))
    q = math.exp(-x + a * math.log(x) - gln) * h
    return max(0.0, min(1.0, q))


def _friedmanchisquare(*samples: Sequence[float]) -> tuple[float, float]:
    if len(samples) < 3:
        raise ValueError("Friedman test requires at least three paired samples.")
    n = len(samples[0])
    if n == 0 or any(len(sample) != n for sample in samples):
        raise ValueError("Friedman samples must have equal non-zero length.")

    k = len(samples)
    rank_sums = [0.0] * k
    for block in zip(*samples):
        ranks = _rankdata([float(value) for value in block])
        for idx, rank in enumerate(ranks):
            rank_sums[idx] += rank
    statistic = (12.0 / (n * k * (k + 1.0))) * sum(r * r for r in rank_sums) - 3.0 * n * (k + 1.0)
    statistic = max(0.0, statistic)
    p_value = _gamma_q((k - 1.0) / 2.0, statistic / 2.0)
    return float(statistic), float(p_value)


METRIC_DIRECTIONS = {
    "hv": False,
    "igd": True,
    "min_total_cost": True,
    "min_makespan": True,
}

ALGORITHM_OFF = ["nsgaii", "moead", "edats-baseline", "mvc-edats"]
ALGORITHM_OFF_PAIRS = [
    ("mvc-edats", "nsgaii"),
    ("mvc-edats", "moead"),
    ("mvc-edats", "edats-baseline"),
    ("edats-baseline", "nsgaii"),
    ("edats-baseline", "moead"),
]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _label(algorithm: str, cross_chain: str | None = None) -> str:
    names = {
        "nsgaii": "NSGA-II",
        "moead": "MOEA/D",
        "edats-baseline": "Plain EDA-TS",
        "mvc-edats": "MVC-EDA-TS",
    }
    base = names.get(algorithm, algorithm)
    return f"{base}-{cross_chain}" if cross_chain else base


def _finite_float(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _merge_pareto(main_dir: Path, plain_dir: Path, combined_dir: Path) -> list[dict]:
    rows: list[dict] = []
    for source, exp_dir in [("main_experiment", main_dir), ("plain_edats_off", plain_dir)]:
        path = exp_dir / "pareto" / "all_pareto_points.csv"
        for row in read_csv(path):
            item = dict(row)
            item["result_source"] = source
            rows.append(item)
    write_csv(combined_dir / "pareto" / "all_pareto_points.csv", rows)
    return rows


def _build_unified_metrics(main_dir: Path, plain_dir: Path, combined_dir: Path) -> list[dict]:
    rows = _merge_pareto(main_dir, plain_dir, combined_dir)
    metrics = summarize_metrics(rows, objective_dim=2)
    write_csv(combined_dir / "metrics" / "metrics_summary.csv", metrics)
    return metrics


def _aggregate_by_instance(metrics: Sequence[Mapping[str, object]]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in metrics:
        key = (str(row.get("instance", "")), str(row.get("algorithm", "")), str(row.get("cross_chain", "")))
        grouped[key].append(row)

    out: list[dict] = []
    for (instance, algorithm, cross_chain), group in sorted(grouped.items()):
        item = {
            "instance": instance,
            "algorithm": algorithm,
            "algorithm_label": _label(algorithm),
            "cross_chain": cross_chain,
            "algorithm_mode": _label(algorithm, cross_chain),
            "seeds": len({str(r.get("seed", "")) for r in group}),
            "runs": len(group),
        }
        for metric in METRIC_DIRECTIONS:
            values = [_finite_float(r.get(metric)) for r in group]
            values = [v for v in values if v is not None]
            if values:
                item[metric] = mean(values)
        out.append(item)
    return out


def _rows_by_instance_mode(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str, str], Mapping[str, object]]:
    return {
        (str(r.get("instance", "")), str(r.get("algorithm", "")), str(r.get("cross_chain", ""))): r
        for r in rows
    }


def _holm_adjust(rows: list[dict], alpha: float) -> list[dict]:
    ordered = sorted(range(len(rows)), key=lambda i: float(rows[i]["p_value"]))
    m = len(rows)
    running = 0.0
    adjusted = [1.0] * len(rows)
    for rank, idx in enumerate(ordered):
        p_value = float(rows[idx]["p_value"])
        adj = min(1.0, (m - rank) * p_value)
        running = max(running, adj)
        adjusted[idx] = running
    for idx, row in enumerate(rows):
        row["adjusted_p"] = adjusted[idx]
        row["significant"] = adjusted[idx] < alpha
    return rows


def _wilcoxon_rows(
    aggregate_rows: Sequence[Mapping[str, object]],
    pairs: Sequence[tuple[tuple[str, str], tuple[str, str]]],
    metrics: Iterable[str],
    family: str,
    alpha: float,
) -> list[dict]:
    by_key = _rows_by_instance_mode(aggregate_rows)
    out: list[dict] = []
    for metric in metrics:
        smaller_is_better = METRIC_DIRECTIONS[metric]
        for (alg_a, cross_a), (alg_b, cross_b) in pairs:
            values_a: list[float] = []
            values_b: list[float] = []
            instances: list[str] = []
            all_instances = sorted({key[0] for key in by_key})
            for instance in all_instances:
                row_a = by_key.get((instance, alg_a, cross_a))
                row_b = by_key.get((instance, alg_b, cross_b))
                if row_a is None or row_b is None:
                    continue
                va = _finite_float(row_a.get(metric))
                vb = _finite_float(row_b.get(metric))
                if va is None or vb is None:
                    continue
                values_a.append(va)
                values_b.append(vb)
                instances.append(instance)
            if not values_a:
                continue
            w_m, p_value, win = wilcoxon_signed_rank(values_a, values_b, alpha=alpha, smaller_is_better=smaller_is_better)
            mean_a = mean(values_a)
            mean_b = mean(values_b)
            if abs(mean_a - mean_b) <= 1e-12:
                better = "tie"
            elif smaller_is_better:
                better = "A" if mean_a < mean_b else "B"
            else:
                better = "A" if mean_a > mean_b else "B"
            out.append(
                {
                    "family": family,
                    "metric": metric,
                    "direction": "lower_better" if smaller_is_better else "higher_better",
                    "comparison": f"{_label(alg_a, cross_a)} vs {_label(alg_b, cross_b)}",
                    "algorithm_a": alg_a,
                    "cross_chain_a": cross_a,
                    "algorithm_b": alg_b,
                    "cross_chain_b": cross_b,
                    "samples": len(values_a),
                    "mean_A": mean_a,
                    "mean_B": mean_b,
                    "better": better,
                    "wilcoxon_W": w_m,
                    "p_value": p_value,
                    "raw_win_if_significant": win,
                    "instances": ";".join(instances),
                }
            )
    return _holm_adjust(out, alpha)


def _friedman_rows(aggregate_rows: Sequence[Mapping[str, object]], alpha: float) -> list[dict]:
    by_key = _rows_by_instance_mode(aggregate_rows)
    out: list[dict] = []
    for metric, smaller_is_better in METRIC_DIRECTIONS.items():
        common_instances = []
        for instance in sorted({key[0] for key in by_key}):
            if all((instance, algorithm, "off") in by_key for algorithm in ALGORITHM_OFF):
                values = [_finite_float(by_key[(instance, algorithm, "off")].get(metric)) for algorithm in ALGORITHM_OFF]
                if all(v is not None for v in values):
                    common_instances.append(instance)
        if len(common_instances) < 2:
            continue
        samples = [
            [float(by_key[(instance, algorithm, "off")][metric]) for instance in common_instances]
            for algorithm in ALGORITHM_OFF
        ]
        statistic, p_value = _friedmanchisquare(*samples)
        rank_sums = {algorithm: [] for algorithm in ALGORITHM_OFF}
        for instance in common_instances:
            values = [float(by_key[(instance, algorithm, "off")][metric]) for algorithm in ALGORITHM_OFF]
            rank_input = values if smaller_is_better else [-v for v in values]
            ranks = _rankdata(rank_input)
            for algorithm, rank in zip(ALGORITHM_OFF, ranks):
                rank_sums[algorithm].append(float(rank))
        for algorithm in ALGORITHM_OFF:
            out.append(
                {
                    "metric": metric,
                    "direction": "lower_better" if smaller_is_better else "higher_better",
                    "algorithm": algorithm,
                    "algorithm_label": _label(algorithm),
                    "samples": len(common_instances),
                    "average_rank": mean(rank_sums[algorithm]),
                    "friedman_statistic": float(statistic),
                    "p_value": float(p_value),
                    "significant": float(p_value) < alpha,
                    "instances": ";".join(common_instances),
                }
            )
    return out


def _summary_markdown(wilcoxon_all: Sequence[Mapping[str, object]], friedman: Sequence[Mapping[str, object]]) -> str:
    lines = [
        "# MVC-SM-DFJSP Statistical Test Summary",
        "",
        "This report is generated from unified metrics recomputed after merging the formal main experiment and Plain EDA-TS-off Pareto points.",
        "",
        "## Wilcoxon Signed-Rank Tests",
        "",
        "| Family | Metric | Comparison | Samples | Mean A | Mean B | Adjusted p | Significant | Better |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in wilcoxon_all:
        lines.append(
            "| {family} | {metric} | {comparison} | {samples} | {mean_A:.6g} | {mean_B:.6g} | {adjusted_p:.6g} | {significant} | {better} |".format(
                **row
            )
        )
    lines.extend(["", "## Friedman Ranking", "", "| Metric | Algorithm | Average rank | p-value | Significant |", "| --- | --- | ---: | ---: | --- |"])
    for row in friedman:
        lines.append(
            "| {metric} | {algorithm_label} | {average_rank:.4g} | {p_value:.6g} | {significant} |".format(**row)
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MVC-SM-DFJSP statistical tests with Plain EDA-TS-off included.")
    parser.add_argument("--main-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/main_experiment")
    parser.add_argument("--plain-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/plain_edats_off")
    parser.add_argument("--combined-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/main_experiment_with_plain_edats")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/stat_tests")
    parser.add_argument("--alpha", type=float, default=0.05)
    args = parser.parse_args()

    main_dir = _resolve(args.main_dir)
    plain_dir = _resolve(args.plain_dir)
    combined_dir = _resolve(args.combined_dir)
    out_dir = _resolve(args.out_dir)

    metrics = _build_unified_metrics(main_dir, plain_dir, combined_dir)
    aggregate_rows = _aggregate_by_instance(metrics)
    write_csv(out_dir / "metrics_by_instance_algorithm_mode.csv", aggregate_rows)

    algorithm_rows = [
        r
        for r in aggregate_rows
        if str(r.get("cross_chain", "")) == "off" and str(r.get("algorithm", "")) in set(ALGORITHM_OFF)
    ]
    write_csv(out_dir / "algorithm_off_comparison_metrics.csv", algorithm_rows)

    mechanism_rows = [
        r
        for r in aggregate_rows
        if str(r.get("algorithm", "")) == "mvc-edats" and str(r.get("cross_chain", "")) in {"off", "on"}
    ]
    write_csv(out_dir / "mechanism_mvc_metrics.csv", mechanism_rows)

    algorithm_pairs = [((a, "off"), (b, "off")) for a, b in ALGORITHM_OFF_PAIRS]
    mechanism_pairs = [(("mvc-edats", "on"), ("mvc-edats", "off"))]

    wilcoxon_hv_igd = []
    wilcoxon_hv_igd.extend(_wilcoxon_rows(aggregate_rows, algorithm_pairs, ["hv", "igd"], "algorithm_off", args.alpha))
    wilcoxon_hv_igd.extend(_wilcoxon_rows(aggregate_rows, mechanism_pairs, ["hv", "igd"], "mechanism_mvc", args.alpha))
    write_csv(out_dir / "wilcoxon_hv_igd.csv", wilcoxon_hv_igd)

    wilcoxon_cost_makespan = []
    wilcoxon_cost_makespan.extend(
        _wilcoxon_rows(aggregate_rows, algorithm_pairs, ["min_total_cost", "min_makespan"], "algorithm_off", args.alpha)
    )
    wilcoxon_cost_makespan.extend(
        _wilcoxon_rows(aggregate_rows, mechanism_pairs, ["min_total_cost", "min_makespan"], "mechanism_mvc", args.alpha)
    )
    write_csv(out_dir / "wilcoxon_cost_makespan.csv", wilcoxon_cost_makespan)

    friedman = _friedman_rows(aggregate_rows, args.alpha)
    write_csv(out_dir / "friedman_ranking.csv", friedman)

    summary = _summary_markdown([*wilcoxon_hv_igd, *wilcoxon_cost_makespan], friedman)
    (out_dir / "stat_tests_summary.md").parent.mkdir(parents=True, exist_ok=True)
    (out_dir / "stat_tests_summary.md").write_text(summary, encoding="utf-8")

    print(f"combined_metrics: {(combined_dir / 'metrics' / 'metrics_summary.csv').as_posix()}")
    print(f"algorithm_off_metrics: {(out_dir / 'algorithm_off_comparison_metrics.csv').as_posix()}")
    print(f"wilcoxon_hv_igd: {(out_dir / 'wilcoxon_hv_igd.csv').as_posix()}")
    print(f"wilcoxon_cost_makespan: {(out_dir / 'wilcoxon_cost_makespan.csv').as_posix()}")
    print(f"friedman_ranking: {(out_dir / 'friedman_ranking.csv').as_posix()}")
    print(f"summary: {(out_dir / 'stat_tests_summary.md').as_posix()}")


if __name__ == "__main__":
    main()
