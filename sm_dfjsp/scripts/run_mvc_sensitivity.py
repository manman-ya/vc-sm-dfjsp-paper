from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from mvc_experiment_utils import (
    ProgressBar,
    ROOT,
    front_rows,
    load_mvc_instance_json,
    parse_csv_list,
    read_csv,
    run_algorithm,
    select_compromise,
    stop_metadata,
    summarize_metrics,
    write_csv,
)
from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.data.mvc_builder import save_mvc_payload


def _scenario_payload(payload: dict, fixed_cost: float, transport_scale: float, cross_time_scale: float) -> dict:
    out = copy.deepcopy(payload)
    for job_key, by_sru in out.get("cross_chain", {}).items():
        for sru_id, item in by_sru.items():
            if item.get("is_cross_chain"):
                item["cross_chain_fixed_cost"] = float(fixed_cost)
                item["cross_chain_cost_rate"] = 0.0
                item["estimated_cross_chain_cost"] = float(fixed_cost)
            else:
                item["cross_chain_fixed_cost"] = 0.0
                item["cross_chain_cost_rate"] = 0.0
                item["estimated_cross_chain_cost"] = 0.0
    for job_key, by_sru in out.get("cross_chain", {}).items():
        for sru_id, item in by_sru.items():
            if not item.get("is_cross_chain"):
                continue
            if job_key in out.get("transport_cost", {}) and sru_id in out["transport_cost"][job_key]:
                out["transport_cost"][job_key][sru_id] = float(round(float(out["transport_cost"][job_key][sru_id]) * transport_scale, 6))
            if job_key in out.get("transport_time", {}) and sru_id in out["transport_time"][job_key]:
                out["transport_time"][job_key][sru_id] = float(round(float(out["transport_time"][job_key][sru_id]) * cross_time_scale, 6))
            job_id = int(str(job_key).lstrip("J"))
            job = next((j for j in out.get("jobs", []) if int(j.get("job_id", -1)) == job_id), None)
            if not job:
                continue
            for op in job.get("operations", []):
                for option in op.get("processing_options_by_sru", {}).get(sru_id, []):
                    option["adjusted_processing_time"] = float(
                        round(float(option["adjusted_processing_time"]) * cross_time_scale, 6)
                    )
    out["instance_name"] = (
        f"{payload.get('instance_name', 'mvc')}"
        f"_cf{fixed_cost:g}_ts{transport_scale:g}_xt{cross_time_scale:g}"
    )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVC-SM-DFJSP sensitivity analysis.")
    parser.add_argument("--input", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty/mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_2obj/sensitivity")
    parser.add_argument("--fixed-costs", default="0,10,20,40")
    parser.add_argument("--transport-cost-scales", default="1.0", help="Multiplier for cross-chain transport cost.")
    parser.add_argument("--cross-time-scales", default="1.0", help="Multiplier for cross-chain transport and processing time; smaller means stronger time advantage.")
    parser.add_argument("--cost-rates", default="0", help="Deprecated; cross-chain variable cost is always 0.")
    parser.add_argument("--cross-modes", default="off,on")
    parser.add_argument("--seed", type=int, default=20260428)
    parser.add_argument("--popsize", type=int, default=8)
    parser.add_argument("--max-iter", type=int, default=2)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--resume", action="store_true", help="Skip sensitivity runs whose raw output files already exist.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    all_rows = []
    selected_rows = []
    tmp_dir = out_dir / "_scenario_instances"
    fixed_costs = [float(x) for x in parse_csv_list(args.fixed_costs)]
    transport_scales = [float(x) for x in parse_csv_list(args.transport_cost_scales)]
    cross_time_scales = [float(x) for x in parse_csv_list(args.cross_time_scales)]
    parsed_cost_rates = [float(x) for x in parse_csv_list(args.cost_rates)]
    if any(abs(x) > 1e-12 for x in parsed_cost_rates):
        print("warning: --cost-rates is deprecated; cross-chain variable cost is forced to 0.")
    cross_modes = parse_csv_list(args.cross_modes)
    progress = ProgressBar(
        len(fixed_costs) * len(transport_scales) * len(cross_time_scales) * len(cross_modes),
        "sensitivity",
    )
    for fixed_cost in fixed_costs:
        for transport_scale in transport_scales:
            for cross_time_scale in cross_time_scales:
                scenario = _scenario_payload(payload, fixed_cost, transport_scale, cross_time_scale)
                scenario_path = tmp_dir / f"{scenario['instance_name']}.json"
                save_mvc_payload(scenario, scenario_path)
                instance = load_mvc_instance_json(scenario_path)
                for cross in cross_modes:
                    run_label = f"cf{fixed_cost:g}_ts{transport_scale:g}_xt{cross_time_scale:g}_{cross}"
                    run_path = out_dir / "raw" / f"{run_label}_runs.csv"
                    selected_path = out_dir / "raw" / f"{run_label}_selected.csv"
                    if args.resume and run_path.exists():
                        rows = read_csv(run_path)
                        selected = read_csv(selected_path)
                        all_rows.extend(rows)
                        selected_rows.extend(selected)
                        progress.update(status=f"skip {run_label}")
                        print(f"\nskip {run_label}: existing output found")
                        continue
                    mode = MVCModeConfig(cross_chain_allowed=cross == "on", objective_dim=args.objective_dim)
                    result, runtime_s = run_algorithm(instance, "mvc-edats", mode, args.seed, args.popsize, args.max_iter, args.time_limit)
                    meta = {
                        "instance": instance.name,
                        "algorithm": "mvc-edats",
                        "fixed_cost": fixed_cost,
                        "transport_scale": transport_scale,
                        "cross_time_scale": cross_time_scale,
                        "cost_rate": 0.0,
                        "cross_chain": cross,
                        "seed": args.seed,
                        "objective_dim": args.objective_dim,
                        "runtime_s": runtime_s,
                    }
                    meta.update(stop_metadata(result, runtime_s))
                    rows, _ = front_rows(instance, result.nd_solutions, mode, meta)
                    all_rows.extend(rows)
                    selected = select_compromise(rows, args.objective_dim)
                    selected_for_run = []
                    if selected:
                        selected_for_run.append(dict(selected))
                        selected_rows.extend(selected_for_run)
                    write_csv(run_path, rows)
                    write_csv(selected_path, selected_for_run)
                    print(
                        f"\ndone cf={fixed_cost:g} ts={transport_scale:g} xt={cross_time_scale:g} "
                        f"cross={cross}: front={len(rows)} stop={meta['stop_reason']} "
                        f"iter={meta['iterations_completed']}"
                    )
                    progress.update(status=f"done {run_label}")

    progress.finish()
    metric_rows = summarize_metrics(all_rows, args.objective_dim)
    write_csv(out_dir / "sensitivity_runs.csv", all_rows)
    write_csv(out_dir / "sensitivity_summary.csv", metric_rows)
    write_csv(out_dir / "sensitivity_selected.csv", selected_rows)
    print(f"runs: {(out_dir / 'sensitivity_runs.csv').as_posix()}")
    print(f"summary: {(out_dir / 'sensitivity_summary.csv').as_posix()}")


if __name__ == "__main__":
    main()
