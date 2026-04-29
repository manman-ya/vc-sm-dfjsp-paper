from __future__ import annotations

import argparse
import csv
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from smdfjsp.baselines import HGATSConfig, NSGAIIConfig, run_eda, run_eda_vns, run_h_gats, run_nsgaii
from smdfjsp.data.io import load_instance_json
from smdfjsp.eda_ts import EDATS, EDATSConfig
from smdfjsp.metrics import build_pf_known, c_metric, gd, igd, wilcoxon_signed_rank

from repro_utils import load_yaml, write_run_meta


FRONT_FIELDS = ["instance", "run", "algorithm", "cost", "makespan"]
METRICS_FIELDS = [
    "instance",
    "run",
    "algorithm",
    "seed",
    "GD",
    "IGD",
    "runtime_s",
    "nd_size",
    "best_cost",
    "best_makespan",
]
CMETRIC_FIELDS = ["instance", "run", "a", "b", "c_ab", "c_ba"]
WILCOXON_FIELDS = ["instance", "competitor", "metric", "Wm", "p_value", "win", "n_runs"]
SUMMARY_FIELDS = [
    "instance",
    "algorithm",
    "mean_GD",
    "std_GD",
    "mean_IGD",
    "std_IGD",
    "mean_runtime_s",
    "std_runtime_s",
    "mean_nd_size",
]


def nd_objectives(nd_solutions) -> List[tuple]:
    objs = []
    for x in nd_solutions:
        if x.objectives is not None:
            objs.append((float(x.objectives[0]), float(x.objectives[1])))
    return objs


def _render_bar(done: int, total: int, width: int = 36) -> str:
    if total <= 0:
        return "[" + "-" * width + "] 0/0"
    ratio = max(0.0, min(1.0, done / total))
    fill = int(round(width * ratio))
    return f"[{'#' * fill}{'-' * (width - fill)}] {done}/{total} ({ratio * 100:5.1f}%)"


def _runner_bundle(inst, seed: int, cfg: dict):
    edats_cfg = EDATSConfig(seed=seed, **cfg["eda_ts"])
    eda_cfg = EDATSConfig(seed=seed, **cfg["eda"])
    eda_vns_cfg = EDATSConfig(seed=seed, **cfg["eda_vns"])
    nsgaii_cfg = NSGAIIConfig(seed=seed, **cfg["nsgaii"])
    h_gats_cfg = HGATSConfig(seed=seed, **cfg["h_gats"])
    return [
        ("EDA-TS", lambda: EDATS(inst, edats_cfg).run()),
        ("EDA", lambda: run_eda(inst, eda_cfg)),
        ("NSGA-II", lambda: run_nsgaii(inst, nsgaii_cfg)),
        ("EDA-VNS", lambda: run_eda_vns(inst, eda_vns_cfg)),
        ("H-GA-TS", lambda: run_h_gats(inst, h_gats_cfg)),
    ]


def _safe_std(vals: List[float]) -> float:
    return statistics.pstdev(vals) if len(vals) > 1 else 0.0


def _read_csv_rows(path: Path) -> List[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fieldnames: List[str], rows: List[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _run_key(row: dict) -> Tuple[str, int]:
    return (str(row["instance"]), int(row["run"]))


def _completed_runs(metrics_rows: List[dict], algo_order: List[str]) -> set[Tuple[str, int]]:
    by_run: Dict[Tuple[str, int], set[str]] = defaultdict(set)
    for row in metrics_rows:
        by_run[_run_key(row)].add(str(row["algorithm"]))
    needed = set(algo_order)
    return {key for key, algos in by_run.items() if needed.issubset(algos)}


def _keep_completed(rows: List[dict], completed: set[Tuple[str, int]]) -> List[dict]:
    return [row for row in rows if _run_key(row) in completed]


def _write_raw_outputs(out_dir: Path, front_rows: List[dict], metrics_run_rows: List[dict], cmetric_run_rows: List[dict]) -> None:
    _write_csv(out_dir / "front_points.csv", FRONT_FIELDS, front_rows)
    _write_csv(out_dir / "metrics_runs.csv", METRICS_FIELDS, metrics_run_rows)
    _write_csv(out_dir / "cmetric_runs.csv", CMETRIC_FIELDS, cmetric_run_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/repro/experiment_01_15_quick.yaml")
    parser.add_argument("--data-dir", default="data/sdmk01-15")
    parser.add_argument("--out-dir", default="reports/repro/compare_01_15")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg_path = root / args.config
    data_dir = root / args.data_dir
    cfg = load_yaml(cfg_path)

    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    n_runs = int(cfg.get("n_runs", 1))
    write_run_meta(
        out_dir,
        cfg_path,
        extra={
            "task": "run_experiments_repeated",
            "n_runs": n_runs,
            "instances": cfg["instances"],
            "data_dir": str(data_dir),
        },
    )

    front_rows: List[dict] = []
    metrics_run_rows: List[dict] = []
    cmetric_run_rows: List[dict] = []
    wilcoxon_rows: List[dict] = []

    instances = list(cfg["instances"])
    algo_order = ["EDA-TS", "EDA", "NSGA-II", "EDA-VNS", "H-GA-TS"]
    if args.resume:
        metrics_run_rows = _read_csv_rows(out_dir / "metrics_runs.csv")
        completed = _completed_runs(metrics_run_rows, algo_order)
        metrics_run_rows = _keep_completed(metrics_run_rows, completed)
        front_rows = _keep_completed(_read_csv_rows(out_dir / "front_points.csv"), completed)
        cmetric_run_rows = _keep_completed(_read_csv_rows(out_dir / "cmetric_runs.csv"), completed)
        print(f"resume: loaded {len(completed)} completed run(s) from {out_dir}")
    else:
        completed = set()

    total_steps = len(instances) * n_runs * len(algo_order)
    done_steps = len(completed) * len(algo_order)
    if not args.no_progress:
        print("Overall Progress " + _render_bar(done_steps, total_steps))

    exp_start = time.time()
    for inst_idx, inst_name in enumerate(instances, start=1):
        print(f"\n=== Instance {inst_name} ({inst_idx}/{len(instances)}) ===")
        inst = load_instance_json(data_dir / f"{inst_name}.json")
        for run_idx in range(1, n_runs + 1):
            if (inst_name, run_idx) in completed:
                print(f"[{inst_name}] run {run_idx}/{n_runs} already complete, skipped")
                continue
            seed = int(cfg["seed"]) + inst_idx * 10000 + run_idx
            print(f"[{inst_name}] run {run_idx}/{n_runs}, seed={seed}")
            runners = _runner_bundle(inst, seed, cfg)
            fronts: Dict[str, List[Tuple[float, float]]] = {}
            runtime_map: Dict[str, float] = {}

            for algo_name, algo_fn in runners:
                t0 = time.time()
                run_result = algo_fn()
                elapsed = time.time() - t0
                front = nd_objectives(run_result.nd_solutions)
                fronts[algo_name] = front
                runtime_map[algo_name] = elapsed

                done_steps += 1
                if not args.no_progress:
                    print("Overall Progress " + _render_bar(done_steps, total_steps))
                if front:
                    print(
                        f"[{inst_name}] run {run_idx:02d} done {algo_name:8s} | "
                        f"nd={len(front):3d} | bestC={min(x[0] for x in front):.3f} "
                        f"| bestMK={min(x[1] for x in front):.3f} | {elapsed:.1f}s"
                    )
                else:
                    print(f"[{inst_name}] run {run_idx:02d} done {algo_name:8s} | nd=0 | {elapsed:.1f}s")

            pf_true = build_pf_known(list(fronts.values()))
            for algo in algo_order:
                front = fronts[algo]
                for c, mk in front:
                    front_rows.append(
                        {
                            "instance": inst_name,
                            "run": run_idx,
                            "algorithm": algo,
                            "cost": c,
                            "makespan": mk,
                        }
                    )
                metrics_run_rows.append(
                    {
                        "instance": inst_name,
                        "run": run_idx,
                        "algorithm": algo,
                        "seed": seed,
                        "GD": gd(front, pf_true),
                        "IGD": igd(front, pf_true),
                        "runtime_s": runtime_map[algo],
                        "nd_size": len(front),
                        "best_cost": min((x[0] for x in front), default=float("inf")),
                        "best_makespan": min((x[1] for x in front), default=float("inf")),
                    }
                )

            for i in range(len(algo_order)):
                for j in range(i + 1, len(algo_order)):
                    a, b = algo_order[i], algo_order[j]
                    cmetric_run_rows.append(
                        {
                            "instance": inst_name,
                            "run": run_idx,
                            "a": a,
                            "b": b,
                            "c_ab": c_metric(fronts[a], fronts[b]),
                            "c_ba": c_metric(fronts[b], fronts[a]),
                        }
                    )

            _write_raw_outputs(out_dir, front_rows, metrics_run_rows, cmetric_run_rows)
            completed.add((inst_name, run_idx))

        # Wilcoxon per instance (EDA-TS vs competitors) on GD/IGD.
        for competitor in ["EDA", "NSGA-II", "EDA-VNS", "H-GA-TS"]:
            base_rows = [
                r for r in metrics_run_rows if r["instance"] == inst_name and r["algorithm"] == "EDA-TS"
            ]
            cmp_rows = [r for r in metrics_run_rows if r["instance"] == inst_name and r["algorithm"] == competitor]
            base_rows = sorted(base_rows, key=lambda x: int(x["run"]))
            cmp_rows = sorted(cmp_rows, key=lambda x: int(x["run"]))
            if len(base_rows) != len(cmp_rows) or not base_rows:
                continue
            for metric in ["GD", "IGD"]:
                a = [float(r[metric]) for r in base_rows]
                b = [float(r[metric]) for r in cmp_rows]
                wm, p, win = wilcoxon_signed_rank(a, b, alpha=0.05, smaller_is_better=True)
                wilcoxon_rows.append(
                    {
                        "instance": inst_name,
                        "competitor": competitor,
                        "metric": metric,
                        "Wm": wm,
                        "p_value": p,
                        "win": win,
                        "n_runs": len(a),
                    }
                )

    # Summary rows.
    grouped: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for row in metrics_run_rows:
        grouped[(str(row["instance"]), str(row["algorithm"]))].append(row)

    summary_rows: List[dict] = []
    for (inst_name, algo), rows in sorted(grouped.items()):
        gd_vals = [float(r["GD"]) for r in rows]
        igd_vals = [float(r["IGD"]) for r in rows]
        rt_vals = [float(r["runtime_s"]) for r in rows]
        nd_vals = [float(r["nd_size"]) for r in rows]
        summary_rows.append(
            {
                "instance": inst_name,
                "algorithm": algo,
                "mean_GD": sum(gd_vals) / len(gd_vals),
                "std_GD": _safe_std(gd_vals),
                "mean_IGD": sum(igd_vals) / len(igd_vals),
                "std_IGD": _safe_std(igd_vals),
                "mean_runtime_s": sum(rt_vals) / len(rt_vals),
                "std_runtime_s": _safe_std(rt_vals),
                "mean_nd_size": sum(nd_vals) / len(nd_vals),
            }
        )

    _write_raw_outputs(out_dir, front_rows, metrics_run_rows, cmetric_run_rows)
    _write_csv(out_dir / "metrics_summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(out_dir / "wilcoxon.csv", WILCOXON_FIELDS, wilcoxon_rows)
    print(f"\ndone. outputs in {out_dir}")
    print(f"elapsed: {(time.time() - exp_start) / 60.0:.2f} min")


if __name__ == "__main__":
    main()

