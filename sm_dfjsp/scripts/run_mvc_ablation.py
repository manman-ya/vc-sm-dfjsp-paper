from __future__ import annotations

import argparse
import json
from pathlib import Path

from mvc_experiment_utils import (
    ProgressBar,
    ROOT,
    front_rows,
    load_mvc_instance_json,
    read_csv,
    run_algorithm,
    select_compromise,
    stop_metadata,
    summarize_metrics,
    write_csv,
)
from smdfjsp.core.mvc_types import MVCModeConfig


VARIANTS = {
    "A0_full": {},
    "A1_no_vc_init": {"use_value_chain_init": False},
    "A2_no_prior": {"use_value_chain_prior": False},
    "A3_no_cross_neighbors": {"use_cross_chain_neighbors": False},
    "A4_no_adaptive_neighborhood": {"use_adaptive_neighborhood": False},
    "A5_no_archive": {"use_nd_memory": False},
}

EXTENDED_VARIANTS = {
    **VARIANTS,
    "E1_no_probability_model": {"use_probability_model": False},
    "E2_no_critical_migration": {"use_critical_migration": False},
    "E3_no_cost_return": {"use_cost_return": False},
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVC-EDA-TS ablation experiments.")
    parser.add_argument("--input", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty/mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_2obj/ablation")
    parser.add_argument("--variant-set", choices=["official", "extended"], default="official")
    parser.add_argument("--seed", type=int, default=20260428)
    parser.add_argument("--popsize", type=int, default=8)
    parser.add_argument("--max-iter", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--cross-chain", choices=["off", "on"], default="on")
    parser.add_argument("--resume", action="store_true", help="Skip variants whose raw output files already exist.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    instance = load_mvc_instance_json(input_path)
    mode = MVCModeConfig(cross_chain_allowed=args.cross_chain == "on", objective_dim=args.objective_dim)
    all_rows = []
    selected_rows = []
    history_rows = []
    variants = VARIANTS if args.variant_set == "official" else EXTENDED_VARIANTS
    progress = ProgressBar(len(variants), "ablation")
    for variant, overrides in variants.items():
        variant_code, variant_name = variant.split("_", 1)
        run_path = out_dir / "raw" / f"{variant}_runs.csv"
        history_path = out_dir / "raw" / f"{variant}_history.csv"
        selected_path = out_dir / "raw" / f"{variant}_selected.csv"
        if args.resume and run_path.exists() and history_path.exists():
            rows = read_csv(run_path)
            history = read_csv(history_path)
            selected = read_csv(selected_path)
            all_rows.extend(rows)
            history_rows.extend(history)
            selected_rows.extend(selected)
            progress.update(status=f"skip {variant}")
            print(f"\nskip {variant}: existing output found")
            continue
        result, runtime_s = run_algorithm(instance, "mvc-edats", mode, args.seed, args.popsize, args.max_iter, args.time_limit, overrides)
        meta = {
            "instance": instance.name,
            "algorithm": "mvc-edats",
            "variant": variant_name,
            "variant_code": variant_code,
            "cross_chain": args.cross_chain,
            "seed": args.seed,
            "objective_dim": args.objective_dim,
            "runtime_s": runtime_s,
        }
        meta.update(stop_metadata(result, runtime_s))
        rows, _ = front_rows(instance, result.nd_solutions, mode, meta)
        all_rows.extend(rows)
        history = [dict(meta, **row) for row in result.history]
        history_rows.extend(history)
        selected = select_compromise(rows, args.objective_dim)
        selected_for_variant = []
        if selected:
            selected_for_variant.append(dict(selected))
            selected_rows.extend(selected_for_variant)
        write_csv(run_path, rows)
        write_csv(history_path, history)
        write_csv(selected_path, selected_for_variant)
        print(
            f"\ndone {variant}: front={len(rows)} runtime_s={runtime_s:.3f} "
            f"stop={meta['stop_reason']} iter={meta['iterations_completed']}"
        )
        progress.update(status=f"done {variant}")

    progress.finish()
    metric_rows = summarize_metrics(all_rows, args.objective_dim)
    write_csv(out_dir / "ablation_runs.csv", all_rows)
    write_csv(out_dir / "ablation_summary.csv", metric_rows)
    write_csv(out_dir / "ablation_selected.csv", selected_rows)
    write_csv(out_dir / "ablation_history.csv", history_rows)
    (out_dir / "run_meta.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"runs: {(out_dir / 'ablation_runs.csv').as_posix()}")
    print(f"summary: {(out_dir / 'ablation_summary.csv').as_posix()}")


if __name__ == "__main__":
    main()
