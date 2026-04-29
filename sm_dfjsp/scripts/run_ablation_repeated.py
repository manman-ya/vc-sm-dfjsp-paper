from __future__ import annotations

import argparse
import csv
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from smdfjsp.data.io import load_instance_json
from smdfjsp.eda_ts import EDATS, EDATSConfig
from smdfjsp.metrics import build_pf_known, c_metric, gd, igd, wilcoxon_signed_rank

from repro_utils import load_yaml, write_run_meta


RUN_FIELDS = ["instance", "run", "algorithm", "seed", "GD", "IGD", "runtime_s_total", "nd_size"]
SUMMARY_FIELDS = ["instance", "algorithm", "mean_GD", "std_GD", "mean_IGD", "std_IGD", "mean_nd_size"]
CMETRIC_FIELDS = ["instance", "run", "pair", "c_ab", "c_ba"]
WILCOXON_FIELDS = ["instance", "competitor", "metric", "Wm", "p_value", "win", "n_runs"]


def to_front(res):
    return [(float(x.objectives[0]), float(x.objectives[1])) for x in res.nd_solutions if x.objectives is not None]


def _safe_std(vals: List[float]) -> float:
    return statistics.pstdev(vals) if len(vals) > 1 else 0.0


def _render_bar(done: int, total: int, width: int = 36) -> str:
    if total <= 0:
        return "[" + "-" * width + "] 0/0"
    ratio = max(0.0, min(1.0, done / total))
    fill = int(round(width * ratio))
    return f"[{'#' * fill}{'-' * (width - fill)}] {done}/{total} ({ratio * 100:5.1f}%)"


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


def _completed_runs(run_rows: List[dict]) -> set[Tuple[str, int]]:
    by_run: Dict[Tuple[str, int], set[str]] = defaultdict(set)
    for row in run_rows:
        by_run[_run_key(row)].add(str(row["algorithm"]))
    needed = {"EDA-TS", "EDA-TS_no_m", "EDA-TS_no_n", "EDA-TS_no_mn"}
    return {key for key, algos in by_run.items() if needed.issubset(algos)}


def _keep_completed(rows: List[dict], completed: set[Tuple[str, int]]) -> List[dict]:
    return [row for row in rows if _run_key(row) in completed]


def _write_raw_outputs(out_dir: Path, run_rows: List[dict], cmetric_rows: List[dict]) -> None:
    _write_csv(out_dir / "ablation_runs.csv", RUN_FIELDS, run_rows)
    _write_csv(out_dir / "ablation_cmetric_runs.csv", CMETRIC_FIELDS, cmetric_rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/repro/ablation_01_15_quick.yaml")
    parser.add_argument("--data-dir", default="data/sdmk01-15")
    parser.add_argument("--out-dir", default="reports/repro/ablation_01_15")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    cfg_path = root / args.config
    data_dir = root / args.data_dir
    cfg = load_yaml(cfg_path)
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_run_meta(out_dir, cfg_path, extra={"task": "run_ablation_repeated", "data_dir": str(data_dir)})

    n_runs = int(cfg.get("n_runs", 1))
    instances = list(cfg["instances"])
    base_cfg = dict(cfg["eda_ts"])
    seed0 = int(cfg["seed"])

    run_rows: List[dict] = []
    cmetric_rows: List[dict] = []
    wilcoxon_rows: List[dict] = []
    if args.resume:
        run_rows = _read_csv_rows(out_dir / "ablation_runs.csv")
        completed = _completed_runs(run_rows)
        run_rows = _keep_completed(run_rows, completed)
        cmetric_rows = _keep_completed(_read_csv_rows(out_dir / "ablation_cmetric_runs.csv"), completed)
        print(f"resume: loaded {len(completed)} completed ablation run(s) from {out_dir}")
    else:
        completed = set()

    total_steps = len(instances) * n_runs
    done_steps = len(completed)
    if not args.no_progress:
        print("Ablation Progress " + _render_bar(done_steps, total_steps))

    start = time.time()
    for inst_idx, name in enumerate(instances, start=1):
        print(f"\n=== ablation {name} ({inst_idx}/{len(instances)}) ===")
        inst = load_instance_json(data_dir / f"{name}.json")
        for run_idx in range(1, n_runs + 1):
            if (name, run_idx) in completed:
                print(f"{name} run {run_idx}/{n_runs} already complete, skipped")
                continue
            seed = seed0 + inst_idx * 10000 + run_idx
            cfg_full = EDATSConfig(seed=seed, **base_cfg)
            cfg_no_m = EDATSConfig(**{**cfg_full.__dict__, "use_multi_population": False})
            cfg_no_n = EDATSConfig(**{**cfg_full.__dict__, "use_nd_memory": False})
            cfg_no_mn = EDATSConfig(
                **{**cfg_full.__dict__, "use_multi_population": False, "use_nd_memory": False}
            )

            t0 = time.time()
            r_full = EDATS(inst, cfg_full).run()
            r_no_m = EDATS(inst, cfg_no_m).run()
            r_no_n = EDATS(inst, cfg_no_n).run()
            r_no_mn = EDATS(inst, cfg_no_mn).run()
            elapsed = time.time() - t0

            fronts = {
                "EDA-TS": to_front(r_full),
                "EDA-TS_no_m": to_front(r_no_m),
                "EDA-TS_no_n": to_front(r_no_n),
                "EDA-TS_no_mn": to_front(r_no_mn),
            }
            pf_true = build_pf_known(list(fronts.values()))

            for algo, front in fronts.items():
                run_rows.append(
                    {
                        "instance": name,
                        "run": run_idx,
                        "algorithm": algo,
                        "seed": seed,
                        "GD": gd(front, pf_true),
                        "IGD": igd(front, pf_true),
                        "runtime_s_total": elapsed,
                        "nd_size": len(front),
                    }
                )

            cmetric_rows.append(
                {
                    "instance": name,
                    "run": run_idx,
                    "pair": "EDA-TS_vs_no_m",
                    "c_ab": c_metric(fronts["EDA-TS"], fronts["EDA-TS_no_m"]),
                    "c_ba": c_metric(fronts["EDA-TS_no_m"], fronts["EDA-TS"]),
                }
            )
            cmetric_rows.append(
                {
                    "instance": name,
                    "run": run_idx,
                    "pair": "EDA-TS_vs_no_n",
                    "c_ab": c_metric(fronts["EDA-TS"], fronts["EDA-TS_no_n"]),
                    "c_ba": c_metric(fronts["EDA-TS_no_n"], fronts["EDA-TS"]),
                }
            )
            cmetric_rows.append(
                {
                    "instance": name,
                    "run": run_idx,
                    "pair": "EDA-TS_vs_no_mn",
                    "c_ab": c_metric(fronts["EDA-TS"], fronts["EDA-TS_no_mn"]),
                    "c_ba": c_metric(fronts["EDA-TS_no_mn"], fronts["EDA-TS"]),
                }
            )
            done_steps += 1
            if not args.no_progress:
                print("Ablation Progress " + _render_bar(done_steps, total_steps))
            _write_raw_outputs(out_dir, run_rows, cmetric_rows)
            completed.add((name, run_idx))
            print(f"{name} run {run_idx}/{n_runs} done")

        # Wilcoxon rows.
        for competitor in ["EDA-TS_no_m", "EDA-TS_no_n", "EDA-TS_no_mn"]:
            base = [r for r in run_rows if r["instance"] == name and r["algorithm"] == "EDA-TS"]
            cmp = [r for r in run_rows if r["instance"] == name and r["algorithm"] == competitor]
            base = sorted(base, key=lambda x: int(x["run"]))
            cmp = sorted(cmp, key=lambda x: int(x["run"]))
            for metric in ["GD", "IGD"]:
                a = [float(r[metric]) for r in base]
                b = [float(r[metric]) for r in cmp]
                wm, p, win = wilcoxon_signed_rank(a, b, alpha=0.05, smaller_is_better=True)
                wilcoxon_rows.append(
                    {
                        "instance": name,
                        "competitor": competitor,
                        "metric": metric,
                        "Wm": wm,
                        "p_value": p,
                        "win": win,
                        "n_runs": len(a),
                    }
                )

    grouped: Dict[Tuple[str, str], List[dict]] = defaultdict(list)
    for row in run_rows:
        grouped[(str(row["instance"]), str(row["algorithm"]))].append(row)
    summary_rows: List[dict] = []
    for (inst_name, algo), rows in sorted(grouped.items()):
        gd_vals = [float(r["GD"]) for r in rows]
        igd_vals = [float(r["IGD"]) for r in rows]
        nd_vals = [float(r["nd_size"]) for r in rows]
        summary_rows.append(
            {
                "instance": inst_name,
                "algorithm": algo,
                "mean_GD": sum(gd_vals) / len(gd_vals),
                "std_GD": _safe_std(gd_vals),
                "mean_IGD": sum(igd_vals) / len(igd_vals),
                "std_IGD": _safe_std(igd_vals),
                "mean_nd_size": sum(nd_vals) / len(nd_vals),
            }
        )

    _write_raw_outputs(out_dir, run_rows, cmetric_rows)
    _write_csv(out_dir / "ablation_summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(out_dir / "ablation_wilcoxon.csv", WILCOXON_FIELDS, wilcoxon_rows)
    print(f"saved to {out_dir}, elapsed={(time.time() - start) / 60.0:.2f} min")


if __name__ == "__main__":
    main()

