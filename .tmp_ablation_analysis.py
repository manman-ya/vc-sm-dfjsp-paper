from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

ROOT = Path(r"D:\code\recode\vc-sm_dfjsp\sm_dfjsp\reports\mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2\ablation_official_on")
df = pd.read_csv(ROOT / "all_instance_ablation_summary.csv")
hist = pd.read_csv(ROOT / "all_instance_ablation_history.csv")
nh = pd.read_csv(ROOT / "analysis" / "ablation_neighborhood_summary.csv")

df["short_instance"] = df["instance"].str.extract(r"(mk\d+)")[0]
hist["short_instance"] = hist["instance"].str.extract(r"(mk\d+)")[0]

metrics = {
    "hv": "high",
    "igd": "low",
    "front_size": "high",
    "spacing": "low",
    "min_total_cost": "low",
    "min_makespan": "low",
    "runtime_s": "low",
    "iterations_completed": "high",
}

def holm(ps):
    ps = np.asarray(ps, float)
    order = np.argsort(ps)
    adjusted = np.empty_like(ps)
    running = 0.0
    m = len(ps)
    for rank, idx in enumerate(order):
        value = min(1.0, (m-rank) * ps[idx])
        running = max(running, value)
        adjusted[idx] = running
    return adjusted.tolist()

def paired_effect(deg):
    deg = np.asarray(deg, float)
    nz = deg[np.abs(deg) > 1e-12]
    if len(nz) == 0:
        return 0.0
    ranks = pd.Series(np.abs(nz)).rank(method="average").to_numpy()
    return float((ranks[nz > 0].sum() - ranks[nz < 0].sum()) / ranks.sum())

def sign_test_two_sided(wins, losses):
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    p = 2.0 * sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, p)

comparisons = []
for metric, direction in metrics.items():
    metric_rows = []
    for variant in ["A1", "A2", "A3", "A4", "A5"]:
        a0 = df[df.variant_code == "A0"][["instance", "seed", metric]].rename(columns={metric:"a0"})
        av = df[df.variant_code == variant][["instance", "seed", metric]].rename(columns={metric:"av"})
        p = a0.merge(av, on=["instance", "seed"], validate="one_to_one")
        deg = p.a0 - p.av if direction == "high" else p.av - p.a0
        tol = 1e-12
        wins = int((deg < -tol).sum())
        losses = int((deg > tol).sum())
        ties = int((np.abs(deg) <= tol).sum())
        pv = sign_test_two_sided(wins, losses)
        base_mean = float(p.a0.mean())
        row = {
            "metric": metric, "variant": variant, "n": len(p),
            "a0_mean": base_mean, "variant_mean": float(p.av.mean()),
            "mean_degradation": float(deg.mean()), "median_degradation": float(np.median(deg)),
            "relative_degradation_pct": float(100*deg.mean()/abs(base_mean)) if base_mean else None,
            "variant_wins": wins, "ties": ties, "variant_losses": losses,
            "sign_test_p": pv, "rank_biserial_degradation": paired_effect(deg),
        }
        metric_rows.append(row)
    adj = holm([r["sign_test_p"] for r in metric_rows])
    for r, q in zip(metric_rows, adj):
        r["holm_p_within_metric"] = q
    comparisons.extend(metric_rows)

# Primary inference uses the 15 independent instances; two seeds are averaged
# within each instance to avoid treating repeated seeds as independent samples.
instance_comparisons = []
for metric, direction in metrics.items():
    metric_rows = []
    piv = df.pivot_table(index="short_instance", columns="variant_code", values=metric, aggfunc="mean")
    for variant in ["A1", "A2", "A3", "A4", "A5"]:
        deg = piv["A0"] - piv[variant] if direction == "high" else piv[variant] - piv["A0"]
        tol = 1e-12
        wins = int((deg < -tol).sum())
        losses = int((deg > tol).sum())
        ties = int((np.abs(deg) <= tol).sum())
        base_mean = float(piv["A0"].mean())
        metric_rows.append({
            "metric":metric, "variant":variant, "n_instances":len(deg),
            "mean_degradation":float(deg.mean()), "median_degradation":float(deg.median()),
            "relative_degradation_pct":float(100*deg.mean()/abs(base_mean)) if base_mean else None,
            "variant_wins":wins, "ties":ties, "variant_losses":losses,
            "sign_test_p":sign_test_two_sided(wins, losses),
            "rank_biserial_degradation":paired_effect(deg.to_numpy()),
        })
    adj = holm([r["sign_test_p"] for r in metric_rows])
    for r, q in zip(metric_rows, adj):
        r["holm_p_within_metric"] = q
    instance_comparisons.extend(metric_rows)

# Instance-level mean effects (two seeds averaged), focused on core quality metrics.
instance_effects = []
for variant in ["A1", "A2", "A3", "A4", "A5"]:
    for metric, direction in {"hv":"high", "igd":"low", "front_size":"high", "min_makespan":"low", "runtime_s":"low"}.items():
        pv = df.pivot_table(index="short_instance", columns="variant_code", values=metric, aggfunc="mean")
        deg = pv["A0"] - pv[variant] if direction == "high" else pv[variant] - pv["A0"]
        for inst, value in deg.items():
            instance_effects.append({"variant":variant, "metric":metric, "instance":inst, "degradation":float(value)})

# Stop reasons and iteration/runtime budget.
budget = []
for v, g in df.groupby("variant_code"):
    counts = g.stop_reason.value_counts().to_dict()
    budget.append({
        "variant":v, "runs":len(g), "stop_reasons":counts,
        "iterations_mean":float(g.iterations_completed.mean()),
        "iterations_median":float(g.iterations_completed.median()),
        "iterations_min":int(g.iterations_completed.min()),
        "full_50_count":int((g.iterations_completed == 50).sum()),
        "runtime_mean":float(g.runtime_s.mean()),
        "runtime_median":float(g.runtime_s.median()),
        "runtime_max":float(g.runtime_s.max()),
    })

# Per-instance budget profile for A0.
a0_budget = df[df.variant_code == "A0"].groupby("short_instance").agg(
    runtime_mean=("runtime_s","mean"), iterations_mean=("iterations_completed","mean"),
    hv_mean=("hv","mean"), igd_mean=("igd","mean"), front_mean=("front_size","mean"),
).reset_index().to_dict("records")

# History checkpoints, using last record at or before a checkpoint for every run.
checkpoints = []
for cp in [1, 10, 25, 50]:
    hcp = hist[hist["iter"] <= cp].sort_values("iter").groupby(["instance","seed","variant_code"], as_index=False).tail(1)
    for v, g in hcp.groupby("variant_code"):
        checkpoints.append({
            "checkpoint":cp, "variant":v, "runs_available":len(g),
            "mean_nd_size":float(g.nd_size.mean()), "median_nd_size":float(g.nd_size.median()),
            "mean_best_cost":float(g.best_cost.mean()), "mean_best_makespan":float(g.best_makespan.mean()),
        })

# Neighborhood totals and reward efficiency.
nh_totals = []
for v, g in nh.groupby("variant_code"):
    generated = float(g.generated.sum())
    accepted = float(g.accepted.sum())
    reward = float(g.reward.sum())
    nh_totals.append({
        "variant":v, "generated":generated, "accepted":accepted, "reward":reward,
        "acceptance_rate":accepted/generated if generated else 0,
        "reward_per_generated":reward/generated if generated else 0,
        "reward_per_accepted":reward/accepted if accepted else 0,
    })

# Cross-seed reproducibility per instance/variant.
seed_stability = []
for v, g in df.groupby("variant_code"):
    piv = g.pivot(index="short_instance", columns="seed", values="hv")
    diffs = (piv.iloc[:,0] - piv.iloc[:,1]).abs()
    seed_stability.append({
        "variant":v, "mean_abs_hv_seed_diff":float(diffs.mean()),
        "median_abs_hv_seed_diff":float(diffs.median()), "max_abs_hv_seed_diff":float(diffs.max()),
    })

result = {
    "shape": {"summary_rows":len(df), "history_rows":len(hist), "instances":int(df.short_instance.nunique()), "seeds":sorted(map(int,df.seed.unique())), "variants":sorted(df.variant_code.unique())},
    "comparisons":comparisons,
    "instance_effects":instance_effects,
    "budget":budget,
    "a0_budget_by_instance":a0_budget,
    "history_checkpoints":checkpoints,
    "neighborhood_totals":nh_totals,
    "seed_stability":seed_stability,
}

hv_matrix = pd.DataFrame(instance_effects)
hv_matrix = hv_matrix[hv_matrix.metric == "hv"].pivot(index="instance", columns="variant", values="degradation").reset_index()
hardest = pd.DataFrame(a0_budget).sort_values("hv_mean").head(6).to_dict("records")
compact = {
    "shape":result["shape"],
    "primary_instance_level_comparisons":instance_comparisons,
    "run_level_comparisons":comparisons,
    "hv_degradation_by_instance":hv_matrix.to_dict("records"),
    "hardest_a0_instances":hardest,
    "budget":budget,
    "history_checkpoints":checkpoints,
    "neighborhood_totals":nh_totals,
    "seed_stability":seed_stability,
}
print(json.dumps(compact, ensure_ascii=False, separators=(",", ":")))
