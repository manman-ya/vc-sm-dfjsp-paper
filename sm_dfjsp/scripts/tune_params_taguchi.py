from __future__ import annotations

import argparse
import csv
from pathlib import Path

from smdfjsp.data.io import load_instance_json
from smdfjsp.eda_ts import EDATS, EDATSConfig
from smdfjsp.metrics import ods

from repro_utils import write_run_meta


TAGUCHI_FIELDS = [
    "trial",
    "alpha",
    "beta",
    "gamma",
    "mu",
    "popsize",
    "epsilon",
    "avg_ods",
    "std_ods",
    "avg_nd_size",
    "runs_per_combo",
]


# L25(5^6) table, same ordering as paper Table 4:
# alpha, beta, gamma, mu, popsize, epsilon
L25 = [
    (1, 1, 1, 1, 1, 1),
    (1, 2, 2, 2, 2, 2),
    (1, 3, 3, 3, 3, 3),
    (1, 4, 4, 4, 4, 4),
    (1, 5, 5, 5, 5, 5),
    (2, 1, 2, 3, 4, 5),
    (2, 2, 3, 4, 5, 1),
    (2, 3, 4, 5, 1, 2),
    (2, 4, 5, 1, 2, 3),
    (2, 5, 1, 2, 3, 4),
    (3, 1, 3, 5, 2, 4),
    (3, 2, 4, 1, 3, 5),
    (3, 3, 5, 2, 4, 1),
    (3, 4, 1, 3, 5, 2),
    (3, 5, 2, 4, 1, 3),
    (4, 1, 4, 2, 5, 3),
    (4, 2, 5, 3, 1, 4),
    (4, 3, 1, 4, 2, 5),
    (4, 4, 2, 5, 3, 1),
    (4, 5, 3, 1, 4, 2),
    (5, 1, 5, 4, 3, 2),
    (5, 2, 1, 5, 4, 3),
    (5, 3, 2, 1, 5, 4),
    (5, 4, 3, 2, 1, 5),
    (5, 5, 4, 3, 2, 1),
]

LEVELS = {
    "alpha": [0.1, 0.2, 0.3, 0.4, 0.5],
    "beta": [0.1, 0.2, 0.3, 0.4, 0.5],
    "gamma": [0.1, 0.2, 0.3, 0.4, 0.5],
    "mu": [0.1, 0.2, 0.3, 0.4, 0.5],
    "popsize": [50, 100, 150, 200, 250],
    "epsilon": [0.001, 0.002, 0.005, 0.008, 0.01],
}


def _render_bar(done: int, total: int, width: int = 36) -> str:
    if total <= 0:
        return "[" + "-" * width + "] 0/0"
    ratio = max(0.0, min(1.0, done / total))
    fill = int(round(width * ratio))
    return f"[{'#' * fill}{'-' * (width - fill)}] {done}/{total} ({ratio * 100:5.1f}%)"


def _read_csv_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_taguchi_rows(path: Path, rows: list[dict]) -> None:
    rows = sorted(rows, key=lambda r: int(r["trial"]))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=TAGUCHI_FIELDS)
        w.writeheader()
        w.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--instance", default="sdmk15")
    parser.add_argument("--data-dir", default="data/sdmk01-15")
    parser.add_argument("--runs-per-combo", type=int, default=1)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--max-iter", type=int, default=30)
    parser.add_argument("--out-dir", default="reports/repro/taguchi")
    parser.add_argument("--seed", type=int, default=20260408)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    data_dir = root / args.data_dir
    inst = load_instance_json(data_dir / f"{args.instance}.json")
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    write_run_meta(
        out_dir,
        config_path=None,
        extra={
            "task": "tune_params_taguchi",
            "instance": args.instance,
            "runs_per_combo": args.runs_per_combo,
            "time_limit": args.time_limit,
            "max_iter": args.max_iter,
            "data_dir": str(data_dir),
        },
    )

    out_csv = out_dir / "taguchi_results.csv"
    rows = _read_csv_rows(out_csv) if args.resume else []
    completed_trials = {int(r["trial"]) for r in rows}
    if args.resume:
        print(f"resume: loaded {len(completed_trials)} completed Taguchi trial(s) from {out_csv}")
    print("Taguchi Progress " + _render_bar(len(completed_trials), len(L25)))

    for trial_id, lv in enumerate(L25, start=1):
        if trial_id in completed_trials:
            print(f"trial {trial_id}/25 already complete, skipped")
            continue
        a, b, g, m, p, e = lv
        ods_vals = []
        nd_sizes = []
        for run_idx in range(1, args.runs_per_combo + 1):
            print(
                f"trial {trial_id}/25 run {run_idx}/{args.runs_per_combo} "
                + _render_bar(run_idx - 1, args.runs_per_combo, width=20)
            )
            cfg = EDATSConfig(
                popsize=LEVELS["popsize"][p - 1],
                max_iter=args.max_iter,
                time_limit_s=args.time_limit,
                alpha=LEVELS["alpha"][a - 1],
                beta=LEVELS["beta"][b - 1],
                gamma=LEVELS["gamma"][g - 1],
                mu=LEVELS["mu"][m - 1],
                epsilon=LEVELS["epsilon"][e - 1],
                tmax=5,
                seed=args.seed + trial_id * 100 + run_idx,
            )
            result = EDATS(inst, cfg).run()
            front = [(x.objectives[0], x.objectives[1]) for x in result.nd_solutions if x.objectives is not None]
            ods_vals.append(ods(front))
            nd_sizes.append(len(front))
            print(
                f"trial {trial_id}/25 run {run_idx}/{args.runs_per_combo} done "
                + _render_bar(run_idx, args.runs_per_combo, width=20)
            )
        rows.append(
            {
                "trial": trial_id,
                "alpha": LEVELS["alpha"][a - 1],
                "beta": LEVELS["beta"][b - 1],
                "gamma": LEVELS["gamma"][g - 1],
                "mu": LEVELS["mu"][m - 1],
                "popsize": LEVELS["popsize"][p - 1],
                "epsilon": LEVELS["epsilon"][e - 1],
                "avg_ods": sum(ods_vals) / len(ods_vals),
                "std_ods": (0.0 if len(ods_vals) <= 1 else float((sum((x - (sum(ods_vals) / len(ods_vals))) ** 2 for x in ods_vals) / len(ods_vals)) ** 0.5)),
                "avg_nd_size": sum(nd_sizes) / len(nd_sizes),
                "runs_per_combo": args.runs_per_combo,
            }
        )
        completed_trials.add(trial_id)
        _write_taguchi_rows(out_csv, rows)
        print(f"trial {trial_id}/25 done")
        print("Taguchi Progress " + _render_bar(len(completed_trials), len(L25)))

    _write_taguchi_rows(out_csv, rows)
    print(f"saved: {out_csv}")


if __name__ == "__main__":
    main()

