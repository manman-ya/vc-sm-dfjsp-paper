from __future__ import annotations

import argparse
import json
from pathlib import Path

from mvc_experiment_utils import (
    ProgressBar,
    ROOT,
    front_rows,
    load_instances,
    load_mvc_instance_json,
    parse_int_list,
    parse_csv_list,
    read_csv,
    run_algorithm,
    select_compromise,
    stop_metadata,
    summarize_metrics,
    write_csv,
)
from run_mvc_ablation import EXTENDED_VARIANTS, VARIANTS
from smdfjsp.core.mvc_types import MVCModeConfig
from build_mvc_ablation_summary import build_ablation_summary


def _short_instance(name: str) -> str:
    return name.split("_mvc_", 1)[0]


def _filter_instances(paths: list[Path], names: str) -> list[Path]:
    wanted = {item.lower() for item in parse_csv_list(names)}
    if not wanted:
        return paths
    return [path for path in paths if path.name.split("_mvc_", 1)[0].lower() in wanted]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full-instance MVC-EDA-TS ablation experiments with a global progress bar.")
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_2obj/ablation")
    parser.add_argument("--variant-set", choices=["official", "extended"], default="official")
    parser.add_argument("--seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--popsize", type=int, default=50)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--time-limit", type=float, default=6000.0)
    parser.add_argument(
        "--max-evaluations",
        type=int,
        default=None,
        help="Optional objective-function evaluation budget shared by every ablation variant.",
    )
    parser.add_argument(
        "--time-measure",
        choices=["wall", "cpu"],
        default="wall",
        help="Clock used for --time-limit; cpu uses process CPU time.",
    )
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--cross-chain", choices=["off", "on"], default="on")
    parser.add_argument("--instances", default="", help="Optional comma-separated short instance names, e.g. mk05,mk10,mk15.")
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip variant runs whose raw output files already exist.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    instance_paths = _filter_instances(load_instances(args.input_dir, args.max_instances), args.instances)
    seeds = parse_int_list(args.seeds)
    variants = VARIANTS if args.variant_set == "official" else EXTENDED_VARIANTS
    mode = MVCModeConfig(cross_chain_allowed=args.cross_chain == "on", objective_dim=args.objective_dim)

    all_rows = []
    all_selected = []
    all_history = []
    progress = ProgressBar(len(instance_paths) * len(seeds) * len(variants), "full ablation")

    for path in instance_paths:
        instance = load_mvc_instance_json(path)
        short = _short_instance(instance.name)
        for seed in seeds:
            seed_dir = out_dir / "by_instance" / short / f"seed{seed}"
            seed_rows = []
            seed_selected = []
            seed_history = []
            for variant, overrides in variants.items():
                variant_code, variant_name = variant.split("_", 1)
                run_path = seed_dir / "raw" / f"{variant}_runs.csv"
                history_path = seed_dir / "raw" / f"{variant}_history.csv"
                selected_path = seed_dir / "raw" / f"{variant}_selected.csv"
                if args.resume and run_path.exists() and history_path.exists():
                    rows = read_csv(run_path)
                    history = read_csv(history_path)
                    selected = read_csv(selected_path)
                    seed_rows.extend(rows)
                    seed_history.extend(history)
                    seed_selected.extend(selected)
                    progress.update(status=f"skip {short} seed{seed} {variant_code}")
                    print(f"\nskip {short} seed{seed} {variant}: existing output found")
                    continue

                result, runtime_s = run_algorithm(
                    instance,
                    "mvc-edats",
                    mode,
                    seed,
                    args.popsize,
                    args.max_iter,
                    args.time_limit,
                    overrides,
                    max_evaluations=args.max_evaluations,
                    time_measure=args.time_measure,
                )
                meta = {
                    "instance": instance.name,
                    "source_instance": instance.metadata.get("source_instance", ""),
                    "algorithm": "mvc-edats",
                    "variant": variant_name,
                    "variant_code": variant_code,
                    "cross_chain": args.cross_chain,
                    "seed": seed,
                    "objective_dim": args.objective_dim,
                    "runtime_s": runtime_s,
                }
                meta.update(stop_metadata(result, runtime_s))
                rows, _ = front_rows(instance, result.nd_solutions, mode, meta)
                history = [dict(meta, **row) for row in result.history]
                selected_for_variant = []
                selected = select_compromise(rows, args.objective_dim)
                if selected:
                    selected_for_variant.append(dict(selected))

                write_csv(run_path, rows)
                write_csv(history_path, history)
                write_csv(selected_path, selected_for_variant)
                seed_rows.extend(rows)
                seed_history.extend(history)
                seed_selected.extend(selected_for_variant)
                print(
                    f"\ndone {short} seed{seed} {variant}: front={len(rows)} runtime_s={runtime_s:.3f} "
                    f"stop={meta['stop_reason']} iter={meta['iterations_completed']}"
                )
                progress.update(status=f"done {short} seed{seed} {variant_code}")

            seed_summary = summarize_metrics(seed_rows, args.objective_dim)
            write_csv(seed_dir / "ablation_runs.csv", seed_rows)
            write_csv(seed_dir / "ablation_summary.csv", seed_summary)
            write_csv(seed_dir / "ablation_selected.csv", seed_selected)
            write_csv(seed_dir / "ablation_history.csv", seed_history)
            all_rows.extend(seed_rows)
            all_selected.extend(seed_selected)
            all_history.extend(seed_history)

    progress.finish()
    all_summary = summarize_metrics(all_rows, args.objective_dim)
    write_csv(out_dir / "all_instance_ablation_runs.csv", all_rows)
    write_csv(out_dir / "all_instance_ablation_summary.csv", all_summary)
    write_csv(out_dir / "all_instance_ablation_selected.csv", all_selected)
    write_csv(out_dir / "all_instance_ablation_history.csv", all_history)
    analysis_dir = build_ablation_summary(out_dir)
    (out_dir / "run_meta.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"out_dir: {out_dir.as_posix()}")
    print(f"summary: {(out_dir / 'all_instance_ablation_summary.csv').as_posix()}")
    print(f"analysis: {analysis_dir.as_posix()}")


if __name__ == "__main__":
    main()
