from __future__ import annotations

import argparse
import math
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mvc_experiment_utils import read_csv, summarize_metrics, write_csv


METRICS = [
    ("hv", "higher"),
    ("igd", "lower"),
    ("front_size", "higher"),
    ("spacing", "lower"),
    ("min_total_cost", "lower"),
    ("min_makespan", "lower"),
    ("mean_cross_chain_ratio", "context"),
    ("mean_sru_load_std", "lower"),
    ("runtime_s", "context"),
]

MODULE_FOCUS = {
    "A1": "value-chain initialization",
    "A2": "value-chain prior",
    "A3": "cross-chain neighbors",
    "A4": "adaptive neighborhood",
    "A5": "non-dominated archive",
}


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _float(value: object) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _short_instance(name: str) -> str:
    return str(name).split("_mvc_", 1)[0]


def _metric_values(rows: Sequence[Mapping[str, object]], metric: str) -> list[float]:
    values = [_float(row.get(metric)) for row in rows]
    return [v for v in values if v is not None]


def _aggregate_variant(rows: Sequence[Mapping[str, object]]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        key = (str(row.get("variant_code", "")), str(row.get("variant", "")), str(row.get("cross_chain", "")))
        grouped[key].append(row)

    out: list[dict] = []
    for (variant_code, variant, cross_chain), group in sorted(grouped.items()):
        item: dict[str, object] = {
            "variant_code": variant_code,
            "variant": variant,
            "cross_chain": cross_chain,
            "instances": len({str(r.get("instance", "")) for r in group}),
            "seeds": len({str(r.get("seed", "")) for r in group}),
            "runs": len(group),
        }
        for metric, _direction in METRICS:
            values = _metric_values(group, metric)
            if not values:
                continue
            item[f"mean_{metric}"] = mean(values)
            item[f"std_{metric}"] = pstdev(values) if len(values) > 1 else 0.0
            item[f"best_{metric}"] = max(values) if _direction == "higher" else min(values)
        out.append(item)
    return out


def _aggregate_instance_variant(rows: Sequence[Mapping[str, object]]) -> list[dict]:
    grouped: dict[tuple[str, str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        key = (
            str(row.get("instance", "")),
            str(row.get("variant_code", "")),
            str(row.get("variant", "")),
            str(row.get("cross_chain", "")),
        )
        grouped[key].append(row)

    out: list[dict] = []
    for (instance, variant_code, variant, cross_chain), group in sorted(grouped.items()):
        item: dict[str, object] = {
            "instance": instance,
            "short_instance": _short_instance(instance),
            "variant_code": variant_code,
            "variant": variant,
            "cross_chain": cross_chain,
            "seeds": len({str(r.get("seed", "")) for r in group}),
            "runs": len(group),
        }
        for metric, _direction in METRICS:
            values = _metric_values(group, metric)
            if values:
                item[metric] = mean(values)
        out.append(item)
    return out


def _effect_vs_full(instance_variant_rows: Sequence[Mapping[str, object]]) -> list[dict]:
    by_key = {
        (str(row.get("instance", "")), str(row.get("cross_chain", "")), str(row.get("variant_code", ""))): row
        for row in instance_variant_rows
    }
    out: list[dict] = []
    for (instance, cross_chain, variant_code), row in sorted(by_key.items()):
        if variant_code == "A0":
            continue
        full = by_key.get((instance, cross_chain, "A0"))
        if full is None:
            continue
        item: dict[str, object] = {
            "instance": instance,
            "short_instance": _short_instance(instance),
            "cross_chain": cross_chain,
            "variant_code": variant_code,
            "variant": row.get("variant", ""),
            "module": MODULE_FOCUS.get(variant_code, ""),
        }
        for metric, direction in METRICS:
            value = _float(row.get(metric))
            baseline = _float(full.get(metric))
            if value is None or baseline is None:
                continue
            delta = value - baseline
            if direction == "higher":
                degradation = -delta
                improved = delta > 0
            elif direction == "lower":
                degradation = delta
                improved = delta < 0
            else:
                degradation = delta
                improved = ""
            item[f"{metric}_full"] = baseline
            item[f"{metric}_variant"] = value
            item[f"{metric}_delta"] = delta
            item[f"{metric}_relative_delta_pct"] = (delta / baseline * 100.0) if abs(baseline) > 1e-12 else ""
            item[f"{metric}_degradation"] = degradation
            item[f"{metric}_improved"] = improved
        out.append(item)
    return out


def _module_indicators(effect_rows: Sequence[Mapping[str, object]]) -> list[dict]:
    grouped: dict[tuple[str, str, str], list[Mapping[str, object]]] = defaultdict(list)
    for row in effect_rows:
        key = (str(row.get("variant_code", "")), str(row.get("variant", "")), str(row.get("module", "")))
        grouped[key].append(row)

    out: list[dict] = []
    focus_metrics = ["hv", "igd", "min_makespan", "front_size", "mean_cross_chain_ratio", "mean_sru_load_std"]
    for (variant_code, variant, module), group in sorted(grouped.items()):
        item: dict[str, object] = {
            "variant_code": variant_code,
            "variant": variant,
            "module": module,
            "instances": len({str(r.get("instance", "")) for r in group}),
        }
        for metric in focus_metrics:
            degradations = _metric_values(group, f"{metric}_degradation")
            deltas = _metric_values(group, f"{metric}_delta")
            if degradations:
                item[f"mean_{metric}_degradation"] = mean(degradations)
                item[f"worse_count_{metric}"] = sum(1 for x in degradations if x > 0)
            if deltas:
                item[f"mean_{metric}_delta"] = mean(deltas)
        out.append(item)
    return out


def _neighborhood_summary(history_rows: Sequence[Mapping[str, object]]) -> list[dict]:
    grouped: dict[tuple[str, str, str], dict[str, float]] = defaultdict(lambda: {"generated": 0.0, "accepted": 0.0, "reward": 0.0})
    for row in history_rows:
        variant_code = str(row.get("variant_code", ""))
        variant = str(row.get("variant", ""))
        for key, value in row.items():
            key = str(key)
            if key.startswith("nh_generated_"):
                kind = key.replace("nh_generated_", "")
                grouped[(variant_code, variant, kind)]["generated"] += float(value or 0.0)
            elif key.startswith("nh_accepted_"):
                kind = key.replace("nh_accepted_", "")
                grouped[(variant_code, variant, kind)]["accepted"] += float(value or 0.0)
            elif key.startswith("nh_reward_"):
                kind = key.replace("nh_reward_", "")
                grouped[(variant_code, variant, kind)]["reward"] += float(value or 0.0)

    out = []
    for (variant_code, variant, kind), values in sorted(grouped.items()):
        generated = values["generated"]
        accepted = values["accepted"]
        out.append(
            {
                "variant_code": variant_code,
                "variant": variant,
                "neighborhood": kind,
                "generated": generated,
                "accepted": accepted,
                "reward": values["reward"],
                "acceptance_rate": accepted / generated if generated > 0 else 0.0,
            }
        )
    return out


def _write_report(out_dir: Path, variant_summary: Sequence[Mapping[str, object]], module_rows: Sequence[Mapping[str, object]]) -> None:
    lines = [
        "# MVC-SM-DFJSP Expanded Ablation Summary",
        "",
        "This report is generated by `scripts/build_mvc_ablation_summary.py`.",
        "",
        "## Variant Summary",
        "",
        "| Variant | Module | Runs | Mean HV | Mean IGD | Mean min cost | Mean min makespan | Mean front size |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    module_by_code = {"A0": "full algorithm", **MODULE_FOCUS}
    for row in variant_summary:
        code = str(row.get("variant_code", ""))
        lines.append(
            "| {code}-{variant} | {module} | {runs} | {hv:.6g} | {igd:.6g} | {cost:.6g} | {mk:.6g} | {front:.6g} |".format(
                code=code,
                variant=row.get("variant", ""),
                module=module_by_code.get(code, ""),
                runs=row.get("runs", ""),
                hv=float(row.get("mean_hv", 0.0)),
                igd=float(row.get("mean_igd", 0.0)),
                cost=float(row.get("mean_min_total_cost", 0.0)),
                mk=float(row.get("mean_min_makespan", 0.0)),
                front=float(row.get("mean_front_size", 0.0)),
            )
        )

    lines.extend(
        [
            "",
            "## Module Effect Versus Full",
            "",
            "| Variant | Module | Instances | Mean HV degradation | Mean IGD degradation | Mean makespan degradation | Mean front-size degradation |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in module_rows:
        lines.append(
            "| {code}-{variant} | {module} | {instances} | {hv:.6g} | {igd:.6g} | {mk:.6g} | {front:.6g} |".format(
                code=row.get("variant_code", ""),
                variant=row.get("variant", ""),
                module=row.get("module", ""),
                instances=row.get("instances", ""),
                hv=float(row.get("mean_hv_degradation", 0.0)),
                igd=float(row.get("mean_igd_degradation", 0.0)),
                mk=float(row.get("mean_min_makespan_degradation", 0.0)),
                front=float(row.get("mean_front_size_degradation", 0.0)),
            )
        )
    lines.append("")
    (out_dir / "ablation_summary_report.md").write_text("\n".join(lines), encoding="utf-8")


def build_ablation_summary(ablation_dir: str | Path) -> Path:
    out_dir = _resolve(ablation_dir)
    runs_path = out_dir / "all_instance_ablation_runs.csv"
    if not runs_path.exists():
        runs_path = out_dir / "ablation_runs.csv"
    summary_path = out_dir / "all_instance_ablation_summary.csv"
    history_path = out_dir / "all_instance_ablation_history.csv"
    if not summary_path.exists():
        summary_path = out_dir / "ablation_summary.csv"
    if not history_path.exists():
        history_path = out_dir / "ablation_history.csv"

    if runs_path.exists():
        rows = summarize_metrics(read_csv(runs_path), objective_dim=2)
        write_csv(summary_path, rows)
    else:
        rows = read_csv(summary_path)
    history_rows = read_csv(history_path)

    variant_summary = _aggregate_variant(rows)
    instance_variant = _aggregate_instance_variant(rows)
    effects = _effect_vs_full(instance_variant)
    module_rows = _module_indicators(effects)
    neighborhood_rows = _neighborhood_summary(history_rows)

    analysis_dir = out_dir / "analysis"
    write_csv(analysis_dir / "ablation_variant_summary.csv", variant_summary)
    write_csv(analysis_dir / "ablation_instance_variant_metrics.csv", instance_variant)
    write_csv(analysis_dir / "ablation_effect_vs_full.csv", effects)
    write_csv(analysis_dir / "ablation_module_indicators.csv", module_rows)
    write_csv(analysis_dir / "ablation_neighborhood_summary.csv", neighborhood_rows)
    _write_report(analysis_dir, variant_summary, module_rows)
    return analysis_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build paper-ready summaries for MVC expanded ablation results.")
    parser.add_argument("--ablation-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/ablation_expanded")
    args = parser.parse_args()
    analysis_dir = build_ablation_summary(args.ablation_dir)
    print(f"analysis_dir: {analysis_dir.as_posix()}")
    print(f"variant_summary: {(analysis_dir / 'ablation_variant_summary.csv').as_posix()}")
    print(f"effect_vs_full: {(analysis_dir / 'ablation_effect_vs_full.csv').as_posix()}")
    print(f"report: {(analysis_dir / 'ablation_summary_report.md').as_posix()}")


if __name__ == "__main__":
    main()
