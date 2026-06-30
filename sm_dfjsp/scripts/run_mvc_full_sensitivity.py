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
    parse_csv_list,
    parse_int_list,
    read_csv,
    run_algorithm,
    select_compromise,
    stop_metadata,
    summarize_metrics,
    write_csv,
)
from run_mvc_sensitivity import _scenario_payload
from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.data.mvc_builder import save_mvc_payload


def _short_instance(name: str) -> str:
    return name.split("_mvc_", 1)[0]


def _filter_instances(paths: list[Path], names: str) -> list[Path]:
    wanted = {item.lower() for item in parse_csv_list(names)}
    if not wanted:
        return paths
    return [path for path in paths if path.name.split("_mvc_", 1)[0].lower() in wanted]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full-instance MVC sensitivity analysis with a global progress bar.")
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_2obj/sensitivity")
    parser.add_argument("--fixed-costs", default="0,10,20,40")
    parser.add_argument("--transport-cost-scales", default="0.8,1.0,1.2")
    parser.add_argument("--cross-time-scales", default="0.8,1.0,1.2")
    parser.add_argument("--cost-rates", default="0", help="Deprecated; cross-chain variable cost is always 0.")
    parser.add_argument("--cross-modes", default="off,on")
    parser.add_argument("--seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--popsize", type=int, default=50)
    parser.add_argument("--max-iter", type=int, default=100)
    parser.add_argument("--time-limit", type=float, default=6000.0)
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--instances", default="", help="Optional comma-separated short instance names, e.g. mk05,mk10,mk15.")
    parser.add_argument("--max-instances", type=int, default=None)
    parser.add_argument("--resume", action="store_true", help="Skip sensitivity runs whose raw output files already exist.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    instance_paths = _filter_instances(load_instances(args.input_dir, args.max_instances), args.instances)
    seeds = parse_int_list(args.seeds)
    fixed_costs = [float(x) for x in parse_csv_list(args.fixed_costs)]
    transport_scales = [float(x) for x in parse_csv_list(args.transport_cost_scales)]
    cross_time_scales = [float(x) for x in parse_csv_list(args.cross_time_scales)]
    parsed_cost_rates = [float(x) for x in parse_csv_list(args.cost_rates)]
    if any(abs(x) > 1e-12 for x in parsed_cost_rates):
        print("warning: --cost-rates is deprecated; cross-chain variable cost is forced to 0.")
    cross_modes = parse_csv_list(args.cross_modes)

    total = len(instance_paths) * len(seeds) * len(fixed_costs) * len(transport_scales) * len(cross_time_scales) * len(cross_modes)
    progress = ProgressBar(total, "full sensitivity")
    all_rows = []
    all_selected = []

    for path in instance_paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        base_instance = load_mvc_instance_json(path)
        short = _short_instance(base_instance.name)
        for seed in seeds:
            seed_dir = out_dir / "by_instance" / short / f"seed{seed}"
            tmp_dir = seed_dir / "_scenario_instances"
            seed_rows = []
            seed_selected = []
            for fixed_cost in fixed_costs:
                for transport_scale in transport_scales:
                    for cross_time_scale in cross_time_scales:
                        scenario = _scenario_payload(payload, fixed_cost, transport_scale, cross_time_scale)
                        scenario_path = tmp_dir / f"{scenario['instance_name']}.json"
                        save_mvc_payload(scenario, scenario_path)
                        instance = load_mvc_instance_json(scenario_path)
                        for cross in cross_modes:
                            run_label = f"cf{fixed_cost:g}_ts{transport_scale:g}_xt{cross_time_scale:g}_{cross}"
                            run_path = seed_dir / "raw" / f"{run_label}_runs.csv"
                            selected_path = seed_dir / "raw" / f"{run_label}_selected.csv"
                            if args.resume and run_path.exists():
                                rows = read_csv(run_path)
                                selected = read_csv(selected_path)
                                seed_rows.extend(rows)
                                seed_selected.extend(selected)
                                progress.update(status=f"skip {short} seed{seed} {run_label}")
                                print(f"\nskip {short} seed{seed} {run_label}: existing output found")
                                continue

                            mode = MVCModeConfig(cross_chain_allowed=cross == "on", objective_dim=args.objective_dim)
                            result, runtime_s = run_algorithm(instance, "mvc-edats", mode, seed, args.popsize, args.max_iter, args.time_limit)
                            meta = {
                                "instance": base_instance.name,
                                "scenario_instance": instance.name,
                                "source_instance": base_instance.metadata.get("source_instance", ""),
                                "algorithm": "mvc-edats",
                                "fixed_cost": fixed_cost,
                                "transport_scale": transport_scale,
                                "cross_time_scale": cross_time_scale,
                                "cost_rate": 0.0,
                                "cross_chain": cross,
                                "seed": seed,
                                "objective_dim": args.objective_dim,
                                "runtime_s": runtime_s,
                            }
                            meta.update(stop_metadata(result, runtime_s))
                            rows, _ = front_rows(instance, result.nd_solutions, mode, meta)
                            selected_for_run = []
                            selected = select_compromise(rows, args.objective_dim)
                            if selected:
                                selected_for_run.append(dict(selected))
                            write_csv(run_path, rows)
                            write_csv(selected_path, selected_for_run)
                            seed_rows.extend(rows)
                            seed_selected.extend(selected_for_run)
                            print(
                                f"\ndone {short} seed{seed} {run_label}: front={len(rows)} runtime_s={runtime_s:.3f} "
                                f"stop={meta['stop_reason']} iter={meta['iterations_completed']}"
                            )
                            progress.update(status=f"done {short} seed{seed} {run_label}")

            seed_summary = summarize_metrics(seed_rows, args.objective_dim)
            write_csv(seed_dir / "sensitivity_runs.csv", seed_rows)
            write_csv(seed_dir / "sensitivity_summary.csv", seed_summary)
            write_csv(seed_dir / "sensitivity_selected.csv", seed_selected)
            all_rows.extend(seed_rows)
            all_selected.extend(seed_selected)

    progress.finish()
    all_summary = summarize_metrics(all_rows, args.objective_dim)
    write_csv(out_dir / "all_instance_sensitivity_runs.csv", all_rows)
    write_csv(out_dir / "all_instance_sensitivity_summary.csv", all_summary)
    write_csv(out_dir / "all_instance_sensitivity_selected.csv", all_selected)
    (out_dir / "run_meta.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"out_dir: {out_dir.as_posix()}")
    print(f"summary: {(out_dir / 'all_instance_sensitivity_summary.csv').as_posix()}")


if __name__ == "__main__":
    main()
