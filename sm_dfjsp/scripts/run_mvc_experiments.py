from __future__ import annotations

import argparse
import json
from pathlib import Path

from build_mvc_algorithm_fronts import build_algorithm_fronts
from build_mvc_instance_nd_fronts import build_instance_nd_fronts
from mvc_experiment_utils import (
    ROOT,
    ProgressBar,
    front_rows,
    load_instances,
    load_mvc_instance_json,
    parse_csv_list,
    parse_int_list,
    read_csv,
    run_algorithm,
    select_compromise,
    stop_metadata,
    summarize_metrics,
    write_csv,
)
from smdfjsp.core.mvc_types import MVCModeConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVC-SM-DFJSP main experiments.")
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/main_experiment")
    parser.add_argument("--algorithms", default="nsgaii,moead,edats-baseline,mvc-edats")
    parser.add_argument("--cross-modes", default="off")
    parser.add_argument("--seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--popsize", type=int, default=8)
    parser.add_argument("--max-iter", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument(
        "--max-evaluations",
        type=int,
        default=None,
        help="Optional objective-function evaluation budget, including initialization and local search.",
    )
    parser.add_argument(
        "--time-measure",
        choices=["wall", "cpu"],
        default="wall",
        help="Clock used for --time-limit; cpu uses process CPU time.",
    )
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip runs whose per-run output files already exist.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    algorithms = parse_csv_list(args.algorithms)
    cross_modes = parse_csv_list(args.cross_modes)
    seeds = parse_int_list(args.seeds)
    all_rows = []
    runtime_rows = []
    compromise_rows = []
    instance_paths = load_instances(args.input_dir, args.max_instances)
    progress = ProgressBar(
        len(instance_paths) * len(algorithms) * len(cross_modes) * len(seeds),
        "main comparison",
    )

    for path in instance_paths:
        instance = load_mvc_instance_json(path)
        for algorithm in algorithms:
            for cross in cross_modes:
                mode = MVCModeConfig(cross_chain_allowed=cross == "on", objective_dim=args.objective_dim)
                for seed in seeds:
                    run_label = f"{instance.name}_{algorithm}_{cross}_seed{seed}"
                    solutions_path = out_dir / "raw" / f"{run_label}_solutions.csv"
                    history_path = out_dir / "raw" / f"{run_label}_history.csv"
                    pareto_path = out_dir / "pareto" / f"{run_label}_pareto.csv"
                    if args.resume and solutions_path.exists() and history_path.exists() and pareto_path.exists():
                        rows = read_csv(pareto_path)
                        history = read_csv(history_path)
                        all_rows.extend(rows)
                        selected = select_compromise(rows, args.objective_dim)
                        if selected:
                            compromise_rows.append(dict(selected))
                        meta_source = rows[0] if rows else (history[0] if history else {})
                        runtime_row = {
                                "instance": meta_source.get("instance", instance.name),
                                "source_instance": meta_source.get("source_instance", instance.metadata.get("source_instance", "")),
                                "algorithm": meta_source.get("algorithm", algorithm),
                                "cross_chain": meta_source.get("cross_chain", cross),
                                "seed": meta_source.get("seed", seed),
                                "objective_dim": meta_source.get("objective_dim", args.objective_dim),
                                "runtime_s": meta_source.get("runtime_s", ""),
                                "stop_reason": meta_source.get("stop_reason", ""),
                                "iterations_completed": meta_source.get("iterations_completed", ""),
                                "algorithm_elapsed_s": meta_source.get("algorithm_elapsed_s", ""),
                                "budget_elapsed_s": meta_source.get("budget_elapsed_s", ""),
                                "time_measure": meta_source.get("time_measure", args.time_measure),
                                "front_size": len(rows),
                            }
                        for key, value in meta_source.items():
                            if key == "evaluations_completed" or (key.startswith("module_") and key.endswith("_s")):
                                runtime_row[key] = value
                        runtime_rows.append(runtime_row)
                        progress.update(status=f"skip {run_label}")
                        print(f"\nskip {run_label}: existing output found")
                        continue
                    result, runtime_s = run_algorithm(
                        instance,
                        algorithm,
                        mode,
                        seed,
                        args.popsize,
                        args.max_iter,
                        args.time_limit,
                        max_evaluations=args.max_evaluations,
                        time_measure=args.time_measure,
                    )
                    meta = {
                        "instance": instance.name,
                        "source_instance": instance.metadata.get("source_instance", ""),
                        "algorithm": algorithm,
                        "cross_chain": cross,
                        "seed": seed,
                        "objective_dim": args.objective_dim,
                        "runtime_s": runtime_s,
                    }
                    meta.update(stop_metadata(result, runtime_s))
                    rows, details = front_rows(instance, result.nd_solutions, mode, meta)
                    history = [dict(meta, **row) for row in result.history]
                    all_rows.extend(rows)
                    write_csv(solutions_path, details)
                    write_csv(history_path, history)
                    write_csv(pareto_path, rows)
                    selected = select_compromise(rows, args.objective_dim)
                    if selected:
                        compromise_rows.append(dict(selected))
                    runtime_rows.append({**meta, "front_size": len(rows)})
                    print(
                        f"\ndone {run_label}: front={len(rows)} runtime_s={runtime_s:.3f} "
                        f"stop={meta['stop_reason']} iter={meta['iterations_completed']}"
                    )
                    progress.update(status=f"done {run_label}")

    progress.finish()
    metric_rows = summarize_metrics(all_rows, args.objective_dim)
    write_csv(out_dir / "pareto" / "all_pareto_points.csv", all_rows)
    write_csv(out_dir / "metrics" / "metrics_summary.csv", metric_rows)
    write_csv(out_dir / "raw" / "runtime_summary.csv", runtime_rows)
    write_csv(out_dir / "raw" / "selected_compromise.csv", compromise_rows)
    combined_front_dir = build_instance_nd_fronts(out_dir)
    algorithm_front_dir = build_algorithm_fronts(out_dir)
    (out_dir / "run_meta.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"out_dir: {out_dir.as_posix()}")
    print(f"all_pareto: {(out_dir / 'pareto' / 'all_pareto_points.csv').as_posix()}")
    print(f"metrics: {(out_dir / 'metrics' / 'metrics_summary.csv').as_posix()}")
    print(f"combined_front_plots: {combined_front_dir.as_posix()}")
    print(f"algorithm_front_plots: {algorithm_front_dir.as_posix()}")


if __name__ == "__main__":
    main()
