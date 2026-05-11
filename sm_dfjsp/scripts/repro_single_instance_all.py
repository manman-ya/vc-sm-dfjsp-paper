from __future__ import annotations

import argparse
import csv
import json
import math
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import pandas as pd
import yaml

from smdfjsp.core.encoding import build_option_index, build_random_individual, repair_individual
from smdfjsp.core.random_utils import make_rng
from smdfjsp.data.io import load_instance_json
from smdfjsp.eda_ts import EDATS, EDATSConfig
from smdfjsp.model.evaluator import evaluate_individual
from smdfjsp.model.gurobi_model import solve_with_gurobi


def _run_cmd(cmd: List[str], cwd: Path) -> None:
    print(">>", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _save_yaml(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=False), encoding="utf-8")


def _single_instance_cfg(base_cfg_path: Path, instance: str, n_runs: int | None, time_limit_s: float | None) -> dict:
    cfg = _load_yaml(base_cfg_path)
    cfg["instances"] = [instance]
    if n_runs is not None:
        cfg["n_runs"] = int(n_runs)
    if time_limit_s is not None:
        for key in ("eda_ts", "eda", "eda_vns", "nsgaii", "h_gats"):
            if key in cfg and isinstance(cfg[key], dict) and "time_limit_s" in cfg[key]:
                cfg[key]["time_limit_s"] = float(time_limit_s)
    return cfg


def _single_instance_ablation_cfg(
    base_cfg_path: Path, instance: str, n_runs: int | None, time_limit_s: float | None
) -> dict:
    cfg = _load_yaml(base_cfg_path)
    cfg["instances"] = [instance]
    if n_runs is not None:
        cfg["n_runs"] = int(n_runs)
    if time_limit_s is not None and "eda_ts" in cfg and "time_limit_s" in cfg["eda_ts"]:
        cfg["eda_ts"]["time_limit_s"] = float(time_limit_s)
    return cfg


def _plot_taguchi(taguchi_csv: Path, out_dir: Path) -> None:
    df = pd.read_csv(taguchi_csv)
    if df.empty:
        return

    factors = ["alpha", "beta", "gamma", "mu", "popsize", "epsilon"]
    fig, axes = plt.subplots(2, 3, figsize=(14, 7), dpi=150)
    axes = axes.ravel()
    for i, fac in enumerate(factors):
        ax = axes[i]
        d = df.groupby(fac, as_index=False)["avg_ods"].mean().sort_values(fac)
        ax.plot(d[fac], d["avg_ods"], marker="o", linewidth=1.4)
        ax.set_title(f"{fac} vs Avg ODS")
        ax.set_xlabel(fac)
        ax.set_ylabel("Avg ODS")
        ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_dir / "fig10_taguchi_main_effects.png")
    plt.close(fig)

    # Sensitivity trend: normalized level curves in one chart.
    fig, ax = plt.subplots(figsize=(10, 6), dpi=150)
    for fac in factors:
        d = df.groupby(fac, as_index=False)["avg_ods"].mean().sort_values(fac)
        y = d["avg_ods"].to_numpy(dtype=float)
        y_min = float(y.min())
        y_max = float(y.max())
        if math.isclose(y_min, y_max):
            yn = [0.0 for _ in y]
        else:
            yn = [(v - y_min) / (y_max - y_min) for v in y]
        ax.plot(range(1, len(yn) + 1), yn, marker="o", linewidth=1.3, label=fac)
    ax.set_title("Taguchi Factor-Level Trend (normalized ODS)")
    ax.set_xlabel("Level Index")
    ax.set_ylabel("Normalized Avg ODS")
    ax.set_xticks([1, 2, 3, 4, 5])
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(frameon=False, ncol=3)
    fig.tight_layout()
    fig.savefig(out_dir / "fig11_taguchi_factor_trend.png")
    plt.close(fig)


def _plot_compare_cmetric_box(cmetric_csv: Path, out_png: Path) -> None:
    df = pd.read_csv(cmetric_csv)
    rows = []
    for _, r in df.iterrows():
        a = str(r["a"])
        b = str(r["b"])
        rows.append({"pair": f"C({a},{b})", "value": float(r["c_ab"])})
        rows.append({"pair": f"C({b},{a})", "value": float(r["c_ba"])})
    long_df = pd.DataFrame(rows)
    if long_df.empty:
        return

    # Keep pairs around EDA-TS first for readability.
    pairs = sorted(long_df["pair"].unique(), key=lambda x: (0 if "EDA-TS" in x else 1, x))
    data = [long_df.loc[long_df["pair"] == p, "value"].to_list() for p in pairs]

    fig, ax = plt.subplots(figsize=(max(10, 0.8 * len(pairs)), 6), dpi=150)
    ax.boxplot(data, tick_labels=pairs, patch_artist=True, showmeans=True)
    ax.set_title("Comparison C-metric Distribution")
    ax.set_ylabel("C-metric")
    ax.set_ylim(0.0, 1.0)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    plt.setp(ax.get_xticklabels(), rotation=35, ha="right")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _plot_ablation_cmetric_box(cmetric_csv: Path, out_png: Path) -> None:
    df = pd.read_csv(cmetric_csv)
    rows = []
    for _, r in df.iterrows():
        pair = str(r["pair"])
        rows.append({"pair": f"{pair}:c_ab", "value": float(r["c_ab"])})
        rows.append({"pair": f"{pair}:c_ba", "value": float(r["c_ba"])})
    long_df = pd.DataFrame(rows)
    if long_df.empty:
        return

    pairs = sorted(long_df["pair"].unique())
    data = [long_df.loc[long_df["pair"] == p, "value"].to_list() for p in pairs]

    fig, ax = plt.subplots(figsize=(max(9, 0.9 * len(pairs)), 6), dpi=150)
    ax.boxplot(data, tick_labels=pairs, patch_artist=True, showmeans=True)
    ax.set_title("Ablation C-metric Distribution")
    ax.set_ylabel("C-metric")
    ax.set_ylim(0.0, 1.0)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _dominates(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return (a[0] <= b[0] and a[1] <= b[1]) and (a[0] < b[0] or a[1] < b[1])


def _model_accuracy_report(
    root: Path,
    data_dir: Path,
    instance: str,
    compare_dir: Path,
    out_dir: Path,
    gurobi_time_limit: float,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    inst_path = data_dir / f"{instance}.json"
    inst = load_instance_json(inst_path)

    front_df = pd.read_csv(compare_dir / "front_points.csv")
    edats = front_df[(front_df["instance"] == instance) & (front_df["algorithm"] == "EDA-TS")].copy()
    if edats.empty:
        raise RuntimeError(f"No EDA-TS front points found for {instance} in {compare_dir / 'front_points.csv'}")
    edats_points = [(float(r.cost), float(r.makespan)) for r in edats.itertuples(index=False)]

    status = "unknown"
    gurobi_point: Tuple[float, float] | None = None
    error_msg = ""
    try:
        g_res = solve_with_gurobi(inst, time_limit_s=gurobi_time_limit)
        status = str(g_res.status)
        if math.isfinite(float(g_res.objective_cost)) and math.isfinite(float(g_res.objective_makespan)):
            gurobi_point = (float(g_res.objective_cost), float(g_res.objective_makespan))
    except Exception as exc:  # pragma: no cover
        error_msg = str(exc)

    points_rows = [
        {"instance": instance, "source": "EDA-TS", "cost": c, "makespan": m}
        for c, m in edats_points
    ]
    if gurobi_point is not None:
        points_rows.append(
            {
                "instance": instance,
                "source": "Gurobi",
                "cost": gurobi_point[0],
                "makespan": gurobi_point[1],
            }
        )
    with (out_dir / "model_accuracy_points.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["instance", "source", "cost", "makespan"])
        writer.writeheader()
        writer.writerows(points_rows)

    summary_lines = [f"instance={instance}", f"gurobi_status={status}"]
    if error_msg:
        summary_lines.append(f"gurobi_error={error_msg}")

    gap_rows: List[dict] = []
    if gurobi_point is not None:
        tol = 1e-6
        contains_exact = any(abs(c - gurobi_point[0]) <= tol and abs(m - gurobi_point[1]) <= tol for c, m in edats_points)
        dominated_by_edats = any(_dominates((c, m), gurobi_point) or (abs(c - gurobi_point[0]) <= tol and abs(m - gurobi_point[1]) <= tol) for c, m in edats_points)
        closest = min(
            edats_points,
            key=lambda x: (abs(x[0] - gurobi_point[0]) / max(abs(gurobi_point[0]), 1e-9))
            + (abs(x[1] - gurobi_point[1]) / max(abs(gurobi_point[1]), 1e-9)),
        )
        gap_cost_pct = (closest[0] - gurobi_point[0]) / max(abs(gurobi_point[0]), 1e-9) * 100.0
        gap_mk_pct = (closest[1] - gurobi_point[1]) / max(abs(gurobi_point[1]), 1e-9) * 100.0
        gap_rows.append(
            {
                "instance": instance,
                "gurobi_cost": gurobi_point[0],
                "gurobi_makespan": gurobi_point[1],
                "closest_edats_cost": closest[0],
                "closest_edats_makespan": closest[1],
                "gap_cost_pct": gap_cost_pct,
                "gap_makespan_pct": gap_mk_pct,
                "contains_exact": int(contains_exact),
                "edats_dominates_or_matches_gurobi": int(dominated_by_edats),
            }
        )
        summary_lines += [
            f"contains_exact={int(contains_exact)}",
            f"edats_dominates_or_matches_gurobi={int(dominated_by_edats)}",
            f"closest_gap_cost_pct={gap_cost_pct:.6f}",
            f"closest_gap_makespan_pct={gap_mk_pct:.6f}",
        ]

        fig, ax = plt.subplots(figsize=(8, 6), dpi=150)
        xs = [x[0] for x in edats_points]
        ys = [x[1] for x in edats_points]
        ax.scatter(xs, ys, s=22, alpha=0.7, label="EDA-TS ND points")
        ax.scatter([gurobi_point[0]], [gurobi_point[1]], s=140, marker="*", label="Gurobi", color="#d62728")
        ax.set_title(f"Model Accuracy Check ({instance})")
        ax.set_xlabel("Cost")
        ax.set_ylabel("Makespan")
        ax.grid(alpha=0.25, linestyle="--")
        ax.legend(frameon=False)
        fig.tight_layout()
        fig.savefig(out_dir / "model_accuracy_pareto.png")
        plt.close(fig)

    with (out_dir / "model_accuracy_gap.csv").open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "instance",
                "gurobi_cost",
                "gurobi_makespan",
                "closest_edats_cost",
                "closest_edats_makespan",
                "gap_cost_pct",
                "gap_makespan_pct",
                "contains_exact",
                "edats_dominates_or_matches_gurobi",
            ],
        )
        writer.writeheader()
        writer.writerows(gap_rows)

    (out_dir / "model_accuracy_summary.txt").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")


def _plot_records(ax, records, title: str) -> None:
    lanes = sorted({(r.sru_id, r.machine_id) for r in records}, key=lambda x: (x[0], x[1]))
    lane_pos = {lane: i for i, lane in enumerate(lanes)}
    cmap = plt.get_cmap("tab20")
    job_ids = sorted({r.job_id for r in records})
    colors = {jid: cmap(i % 20) for i, jid in enumerate(job_ids)}

    for r in records:
        y = lane_pos[(r.sru_id, r.machine_id)]
        ax.barh(
            y,
            r.end - r.start,
            left=r.start,
            height=0.72,
            color=colors[r.job_id],
            edgecolor="black",
            linewidth=0.3,
            alpha=0.9,
        )

    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels([f"S{sid}-M{mid}" for sid, mid in lanes], fontsize=8)
    ax.set_xlabel("Time")
    ax.set_ylabel("SRU-Machine")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25, linestyle="--")


def _gantt_best_vs_random(compare_dir: Path, cfg_path: Path, data_dir: Path, instance: str, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    cfg = _load_yaml(cfg_path)
    metrics_runs = pd.read_csv(compare_dir / "metrics_runs.csv")
    row = metrics_runs[
        (metrics_runs["instance"] == instance) & (metrics_runs["algorithm"] == "EDA-TS") & (metrics_runs["run"] == 1)
    ]
    if row.empty:
        raise RuntimeError("Cannot find run=1 EDA-TS seed in metrics_runs.csv")
    seed = int(row.iloc[0]["seed"])

    inst = load_instance_json(data_dir / f"{instance}.json")
    edats_cfg = EDATSConfig(seed=seed, **cfg["eda_ts"])
    best_res = EDATS(inst, edats_cfg).run()
    sols = [x for x in best_res.nd_solutions if x.objectives is not None]
    if not sols:
        raise RuntimeError("EDA-TS produced no feasible non-dominated solution.")
    best = min(sols, key=lambda s: (s.objectives[0], s.objectives[1]))  # type: ignore[index]
    best_ev = evaluate_individual(inst, best)

    option_index = build_option_index(inst)
    rng = make_rng(seed + 9999)
    rnd = build_random_individual(inst, option_index, rng)
    rnd = repair_individual(rnd, inst, option_index, rng)
    rnd_ev = evaluate_individual(inst, rnd)

    fig, axes = plt.subplots(2, 1, figsize=(13, 10), dpi=150, sharex=True)
    _plot_records(
        axes[0],
        best_ev.records,
        f"EDA-TS Best ND Solution ({instance}) cost={best_ev.objectives[0]:.1f}, mk={best_ev.objectives[1]:.1f}",
    )
    _plot_records(
        axes[1],
        rnd_ev.records,
        f"Random Repaired Solution ({instance}) cost={rnd_ev.objectives[0]:.1f}, mk={rnd_ev.objectives[1]:.1f}",
    )
    fig.tight_layout()
    fig.savefig(out_dir / f"gantt_{instance}_best_vs_random.png")
    plt.close(fig)


def _write_manifest(root_out: Path) -> None:
    files = [p for p in root_out.rglob("*") if p.is_file()]
    items = [{"file": str(p.relative_to(root_out)).replace("\\", "/"), "bytes": p.stat().st_size} for p in files]
    (root_out / "artifact_manifest.json").write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", default="sdmk05")
    parser.add_argument("--data-dir", default="data/sdmk01-15_x2_r3r4")
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--out-dir", default="reports/repro/single_instance_all")
    parser.add_argument("--n-runs", type=int, default=None)
    parser.add_argument("--time-limit-s", type=float, default=None)
    parser.add_argument("--taguchi-runs-per-combo", type=int, default=None)
    parser.add_argument("--skip-build-data", action="store_true")
    parser.add_argument("--skip-validation", action="store_true")
    parser.add_argument("--skip-gurobi", action="store_true")
    parser.add_argument("--gurobi-time-limit", type=float, default=120.0)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    out_root = (root / args.out_dir).resolve()
    out_root.mkdir(parents=True, exist_ok=True)

    data_dir = root / args.data_dir
    inst_path = data_dir / f"{args.instance}.json"
    if not inst_path.exists():
        raise FileNotFoundError(f"Instance not found: {inst_path}")

    if not args.skip_build_data:
        if args.data_dir.replace("\\", "/").rstrip("/") == "data/sdmk01-15_x2_r3r4":
            _run_cmd([sys.executable, "scripts/build_sdmk_01_15_x2_r3r4.py"], root)
        else:
            print(f">> using existing dataset only: {data_dir}")
    if not args.skip_validation:
        _run_cmd(
            [
                sys.executable,
                "scripts/validate_sdmk_dataset.py",
                "--data-dir",
                args.data_dir,
                "--out-dir",
                str(out_root / "validation"),
            ],
            root,
        )

    exp_base = root / "configs" / "repro" / ("experiment_01_15_quick.yaml" if args.mode == "quick" else "experiment_01_15.yaml")
    abl_base = root / "configs" / "repro" / ("ablation_01_15_quick.yaml" if args.mode == "quick" else "ablation_01_15.yaml")
    exp_cfg = _single_instance_cfg(exp_base, args.instance, args.n_runs, args.time_limit_s)
    abl_cfg = _single_instance_ablation_cfg(abl_base, args.instance, args.n_runs, args.time_limit_s)

    cfg_dir = out_root / "configs"
    exp_cfg_path = cfg_dir / f"experiment_{args.instance}.yaml"
    abl_cfg_path = cfg_dir / f"ablation_{args.instance}.yaml"
    _save_yaml(exp_cfg_path, exp_cfg)
    _save_yaml(abl_cfg_path, abl_cfg)

    compare_dir = out_root / "compare"
    ablation_dir = out_root / "ablation"
    taguchi_dir = out_root / "taguchi"
    tables_dir = out_root / "tables"
    figs_dir = out_root / "figures"
    model_dir = out_root / "model_accuracy"

    _run_cmd(
        [
            sys.executable,
            "scripts/run_experiments_repeated.py",
            "--config",
            str(exp_cfg_path),
            "--data-dir",
            args.data_dir,
            "--out-dir",
            str(compare_dir),
        ]
        + (["--resume"] if args.resume else []),
        root,
    )
    _run_cmd(
        [
            sys.executable,
            "scripts/run_ablation_repeated.py",
            "--config",
            str(abl_cfg_path),
            "--data-dir",
            args.data_dir,
            "--out-dir",
            str(ablation_dir),
        ]
        + (["--resume"] if args.resume else []),
        root,
    )

    if args.taguchi_runs_per_combo is None:
        taguchi_runs = 2 if args.mode == "quick" else 30
    else:
        taguchi_runs = int(args.taguchi_runs_per_combo)
    taguchi_time_limit = 8.0 if args.mode == "quick" else 100.0
    taguchi_max_iter = 3 if args.mode == "quick" else 100
    _run_cmd(
        [
            sys.executable,
            "scripts/tune_params_taguchi.py",
            "--instance",
            args.instance,
            "--data-dir",
            args.data_dir,
            "--runs-per-combo",
            str(taguchi_runs),
            "--time-limit",
            str(taguchi_time_limit),
            "--max-iter",
            str(taguchi_max_iter),
            "--out-dir",
            str(taguchi_dir),
        ]
        + (["--resume"] if args.resume else []),
        root,
    )

    _run_cmd(
        [
            sys.executable,
            "scripts/build_paper_tables.py",
            "--compare-dir",
            str(compare_dir),
            "--ablation-dir",
            str(ablation_dir),
            "--out-dir",
            str(tables_dir),
        ],
        root,
    )

    _run_cmd(
        [
            sys.executable,
            "scripts/visualize_repro_results.py",
            "--compare-dir",
            str(compare_dir),
            "--config",
            str(exp_cfg_path),
            "--data-dir",
            args.data_dir,
            "--out-dir",
            str(figs_dir),
            "--gantt-instance",
            args.instance,
            "--gantt-algorithm",
            "EDA-TS",
            "--gantt-run",
            "1",
        ],
        root,
    )

    _plot_taguchi(taguchi_dir / "taguchi_results.csv", figs_dir)
    _plot_compare_cmetric_box(compare_dir / "cmetric_runs.csv", figs_dir / "compare_cmetric_boxplot.png")
    _plot_ablation_cmetric_box(ablation_dir / "ablation_cmetric_runs.csv", figs_dir / "ablation_cmetric_boxplot.png")
    _gantt_best_vs_random(compare_dir, exp_cfg_path, data_dir, args.instance, figs_dir)

    if not args.skip_gurobi:
        _model_accuracy_report(
            root=root,
            data_dir=data_dir,
            instance=args.instance,
            compare_dir=compare_dir,
            out_dir=model_dir,
            gurobi_time_limit=float(args.gurobi_time_limit),
        )

    _write_manifest(out_root)
    print(f"done: single-instance full repro outputs in {out_root}")


if __name__ == "__main__":
    main()
