import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import binomtest, wilcoxon


BASE = Path("sm_dfjsp/reports/mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2/ablation_official_on")
FILES = {
    "runs": "all_instance_ablation_runs.csv",
    "selected": "all_instance_ablation_selected.csv",
    "summary": "all_instance_ablation_summary.csv",
    "history": "all_instance_ablation_history.csv",
}
tables = {name: pd.read_csv(BASE / file) for name, file in FILES.items()}

quality = {}
for name, df in tables.items():
    quality[name] = {
        "shape": list(df.shape),
        "columns": list(df.columns),
        "null_columns": {k: int(v) for k, v in df.isna().sum().items() if v},
        "exact_duplicate_rows": int(df.duplicated().sum()),
    }

runs = tables["runs"]
summary = tables["summary"]
instance = pd.read_csv(BASE / "analysis" / "ablation_instance_variant_metrics.csv")
effects = pd.read_csv(BASE / "analysis" / "ablation_effect_vs_full.csv")
neighborhood = pd.read_csv(BASE / "analysis" / "ablation_neighborhood_summary.csv")

key_cols = [c for c in ["instance", "seed", "variant_code", "cross_chain"] if c in runs.columns]
quality["runs"]["key_columns"] = key_cols
quality["runs"]["duplicate_keys"] = int(runs.duplicated(key_cols).sum()) if key_cols else None
quality["runs"]["instances"] = int(runs["instance"].nunique())
quality["runs"]["variants"] = sorted(runs["variant_code"].unique().tolist())
quality["runs"]["seeds"] = sorted([int(x) for x in runs["seed"].unique()])
quality["runs"]["rows_by_variant"] = {k: int(v) for k, v in runs.groupby("variant_code").size().items()}

for col in ["status", "termination_reason", "stop_reason", "timed_out", "iterations", "n_iter", "runtime_s"]:
    if col in runs.columns:
        if runs[col].dtype == object or col in {"status", "termination_reason", "stop_reason", "timed_out"}:
            quality["runs"][col] = {str(k): int(v) for k, v in runs[col].value_counts(dropna=False).items()}
        else:
            quality["runs"][col] = {"min": float(runs[col].min()), "max": float(runs[col].max()), "mean": float(runs[col].mean())}

metric_direction = {
    "hv": "higher",
    "igd": "lower",
    "front_size": "higher",
    "spacing": "lower",
    "min_total_cost": "lower",
    "min_makespan": "lower",
    "mean_sru_load_std": "lower",
    "runtime_s": "lower",
}
codes = ["A1", "A2", "A3", "A4", "A5"]
paired = {}
for code in codes:
    left = instance[instance.variant_code == "A0"].set_index("short_instance")
    right = instance[instance.variant_code == code].set_index("short_instance")
    common = left.index.intersection(right.index)
    variant_result = {}
    for metric, direction in metric_direction.items():
        a = left.loc[common, metric].astype(float)
        b = right.loc[common, metric].astype(float)
        raw = b - a
        rel = raw / a.replace(0, np.nan) * 100
        degradation = -raw if direction == "higher" else raw
        tol = 1e-12
        worse = int((degradation > tol).sum())
        better = int((degradation < -tol).sum())
        tie = int(len(degradation) - worse - better)
        try:
            w = wilcoxon(b, a, zero_method="wilcox", alternative="two-sided", method="auto")
            wp = float(w.pvalue)
            ws = float(w.statistic)
        except ValueError:
            wp = 1.0
            ws = 0.0
        non_ties = worse + better
        sign_p = float(binomtest(min(worse, better), non_ties, 0.5, alternative="two-sided").pvalue) if non_ties else 1.0
        variant_result[metric] = {
            "mean_variant": float(b.mean()),
            "mean_full": float(a.mean()),
            "mean_raw_change": float(raw.mean()),
            "median_raw_change": float(raw.median()),
            "mean_relative_change_pct": float(rel.mean()),
            "median_relative_change_pct": float(rel.median()),
            "worse_better_tie": [worse, better, tie],
            "wilcoxon_stat": ws,
            "wilcoxon_p": wp,
            "sign_test_p": sign_p,
        }
    paired[code] = variant_result

# Holm correction within each metric across the five ablations.
for metric in metric_direction:
    vals = sorted([(paired[c][metric]["wilcoxon_p"], c) for c in codes])
    adjusted = {}
    running = 0.0
    m = len(vals)
    for i, (p, c) in enumerate(vals):
        running = max(running, min(1.0, p * (m - i)))
        adjusted[c] = running
    for c in codes:
        paired[c][metric]["wilcoxon_holm_p"] = float(adjusted[c])

# Seed-level direction agreement against full, retaining the instance as the unit shown to the user.
run_metrics = [m for m in metric_direction if m in runs.columns]
seed_consistency = {}
for code in codes:
    seed_consistency[code] = {}
    for metric in run_metrics:
        piv = runs[runs.variant_code.isin(["A0", code])].pivot_table(
            index=["short_instance", "seed"], columns="variant_code", values=metric, aggfunc="mean"
        ).dropna()
        raw = piv[code] - piv["A0"]
        deg = -raw if metric_direction[metric] == "higher" else raw
        grouped = deg.groupby(level=0)
        counts = {"both_worse": 0, "both_better": 0, "both_tie": 0, "mixed": 0}
        for _, vals in grouped:
            signs = np.sign(vals.to_numpy(dtype=float))
            signs[np.abs(vals.to_numpy(dtype=float)) <= 1e-12] = 0
            if np.all(signs > 0): counts["both_worse"] += 1
            elif np.all(signs < 0): counts["both_better"] += 1
            elif np.all(signs == 0): counts["both_tie"] += 1
            else: counts["mixed"] += 1
        seed_consistency[code][metric] = counts

# Per-instance winners by quality metric, treating exact numerical equality as ties.
winners = {}
for metric, direction in metric_direction.items():
    if metric == "runtime_s":
        continue
    metric_winners = {}
    for inst_name, group in instance.groupby("short_instance"):
        best = group[metric].max() if direction == "higher" else group[metric].min()
        tol = max(1e-12, abs(float(best)) * 1e-10)
        labels = group.loc[(group[metric] - best).abs() <= tol, "variant_code"].tolist()
        metric_winners[inst_name] = labels
    counts = {c: sum(c in v for v in metric_winners.values()) for c in ["A0"] + codes}
    winners[metric] = {"counts_including_ties": counts, "by_instance": metric_winners}

# Neighborhood acceptance and work relative to full.
nb = {}
full_nb = neighborhood[neighborhood.variant_code == "A0"].set_index("neighborhood")
for code in codes:
    cur = neighborhood[neighborhood.variant_code == code].set_index("neighborhood")
    nb[code] = {
        "generated_ratio_vs_full": float(cur.generated.sum() / full_nb.generated.sum()),
        "accepted_ratio_vs_full": float(cur.accepted.sum() / full_nb.accepted.sum()),
        "overall_acceptance_rate": float(cur.accepted.sum() / cur.generated.sum()),
        "full_overall_acceptance_rate": float(full_nb.accepted.sum() / full_nb.generated.sum()),
    }

out = {
    "quality": quality,
    "paired_instance_stats": paired,
    "seed_consistency": seed_consistency,
    "winner_counts": winners,
    "neighborhood": nb,
}
print(json.dumps(out, ensure_ascii=False, indent=2, allow_nan=False))
