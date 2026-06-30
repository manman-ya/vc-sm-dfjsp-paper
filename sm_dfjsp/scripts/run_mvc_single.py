from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import List, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.baselines.mvc_nsgaii import MVCNSGAIIConfig, run_mvc_nsgaii
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.data.mvc_io import load_mvc_instance_json
from smdfjsp.metrics.multiobjective import get_non_dominated_indices
from smdfjsp.model.mvc_evaluator import evaluate_mvc_individual
from smdfjsp.mvc_eda_ts import MVCEDATS, MVCEDATSConfig
from smdfjsp.visualization.mvc_plots import plot_cross_chain_flow, plot_gantt, plot_pareto_3d_projection, plot_pareto_csv, plot_sru_loads


def _parse_cross(value: str) -> bool:
    value = value.strip().lower()
    if value in {"on", "true", "1", "yes", "cross-on"}:
        return True
    if value in {"off", "false", "0", "no", "cross-off"}:
        return False
    raise argparse.ArgumentTypeError("--cross-chain must be on or off")


def _rows(instance: MVCSMDFJSPInstance, solutions: Sequence[EncodedIndividual], mode: MVCModeConfig) -> List[dict]:
    rows: List[dict] = []
    seen = set()
    for idx, sol in enumerate(solutions, start=1):
        ev = evaluate_mvc_individual(instance, sol, mode)
        if not ev.feasible:
            continue
        key = tuple(round(float(x), 8) for x in ev.objectives)
        if key in seen:
            continue
        seen.add(key)
        row = {
            "solution_id": idx,
            "total_cost": ev.total_cost,
            "makespan": ev.makespan,
            "max_sru_load": ev.max_sru_load,
            "cross_chain_jobs": ev.diagnostics.get("cross_chain_jobs", 0),
            "cross_chain_ratio": ev.diagnostics.get("cross_chain_ratio", 0.0),
            "sru_load_std": ev.diagnostics.get("sru_load_std", 0.0),
        }
        row.update(ev.cost_breakdown)
        rows.append(row)
    return rows


def _write_csv(path: Path, rows: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _select_compromise(rows: List[dict]) -> dict | None:
    if not rows:
        return None
    obj_cols = ["total_cost", "makespan"]
    pts = [tuple(float(r[c]) for c in obj_cols) for r in rows]
    nd = [rows[i] for i in get_non_dominated_indices(pts)]
    if not nd:
        return None
    mins = {c: min(float(r[c]) for r in nd) for c in obj_cols}
    maxs = {c: max(float(r[c]) for r in nd) for c in obj_cols}

    def score(row: dict) -> float:
        total = 0.0
        for c in obj_cols:
            span = max(maxs[c] - mins[c], 1e-9)
            total += (float(row[c]) - mins[c]) / span
        return total

    return min(nd, key=score)


def _stop_metadata(result, runtime_s: float) -> dict:
    iterations_completed = int(getattr(result, "iterations_completed", len(getattr(result, "history", []))))
    stop_reason = str(getattr(result, "stop_reason", "") or "")
    if not stop_reason:
        stop_reason = "max_iter" if iterations_completed > 0 else "completed_without_iteration"
    return {
        "stop_reason": stop_reason,
        "iterations_completed": iterations_completed,
        "algorithm_elapsed_s": float(getattr(result, "elapsed_s", runtime_s)),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one MVC-SM-DFJSP instance.")
    parser.add_argument("--input", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty/mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json")
    parser.add_argument("--out-dir", default="reports/mvc_single")
    parser.add_argument("--algorithm", choices=["nsgaii", "mvc-edats"], default="mvc-edats")
    parser.add_argument("--cross-chain", type=_parse_cross, default=True)
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--seed", type=int, default=20260428)
    parser.add_argument("--popsize", type=int, default=40)
    parser.add_argument("--max-iter", type=int, default=40)
    parser.add_argument("--time-limit", type=float, default=30.0)
    parser.add_argument("--skip-gantt", action="store_true", help="do not write gantt.png")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.is_absolute():
        input_path = ROOT / input_path
    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    mode = MVCModeConfig(cross_chain_allowed=bool(args.cross_chain), objective_dim=int(args.objective_dim))
    instance = load_mvc_instance_json(input_path)

    t0 = time.time()
    if args.algorithm == "nsgaii":
        cfg = MVCNSGAIIConfig(
            popsize=int(args.popsize),
            max_iter=int(args.max_iter),
            time_limit_s=float(args.time_limit),
            seed=int(args.seed),
        )
        result = run_mvc_nsgaii(instance, cfg, mode)
    else:
        cfg = MVCEDATSConfig(
            popsize=int(args.popsize),
            max_iter=int(args.max_iter),
            time_limit_s=float(args.time_limit),
            seed=int(args.seed),
        )
        result = MVCEDATS(instance, cfg, mode).run()
    runtime_s = time.time() - t0
    stop_meta = _stop_metadata(result, runtime_s)

    label = "cross-on" if mode.cross_chain_allowed else "cross-off"
    run_dir = out_dir / f"{instance.name}_{args.algorithm}_{label}_{mode.objective_dim}obj_seed{args.seed}"
    rows = _rows(instance, result.nd_solutions, mode)
    _write_csv(run_dir / "pareto_points.csv", rows)
    selected = _select_compromise(rows)
    selected_eval = None
    selected_solution = None
    if selected is not None:
        selected_id = int(selected["solution_id"])
        if 1 <= selected_id <= len(result.nd_solutions):
            selected_solution = result.nd_solutions[selected_id - 1]
            selected_eval = evaluate_mvc_individual(instance, selected_solution, mode)
    summary = {
        "input": str(input_path.as_posix()),
        "instance": instance.name,
        "algorithm": args.algorithm,
        "cross_chain_allowed": mode.cross_chain_allowed,
        "objective_dim": mode.objective_dim,
        "seed": int(args.seed),
        "runtime_s": runtime_s,
        **stop_meta,
        "front_points": len(rows),
        "selected_compromise": selected,
        "history": result.history,
    }
    run_dir.mkdir(parents=True, exist_ok=True)
    _write_json(run_dir / "summary.json", summary)
    if selected_solution is not None and selected_eval is not None:
        _write_json(
            run_dir / "selected_compromise_solution.json",
            {
                "ua": selected_solution.ua,
                "os": selected_solution.os,
                "op": {str(k): v for k, v in selected_solution.op.items()},
                "ms": {str(k): v for k, v in selected_solution.ms.items()},
                "objectives": list(selected_eval.objectives),
                "cost_breakdown": selected_eval.cost_breakdown,
                "diagnostics": selected_eval.diagnostics,
            },
        )
        _write_csv(run_dir / "selected_schedule.csv", [asdict(r) for r in selected_eval.records])
        _write_csv(run_dir / "sru_loads.csv", [{"sru_id": k, "load": v} for k, v in selected_eval.sru_loads.items()])
        flow = selected_eval.diagnostics.get("cross_chain_flow", {})
        _write_csv(run_dir / "cross_chain_flow.csv", [{"flow": k, "jobs": v} for k, v in dict(flow).items()])
        plot_pareto_csv(rows, run_dir / "pareto.png", f"{instance.name} {args.algorithm} {label}")
        plot_pareto_3d_projection(rows, run_dir / "pareto_3d.png", f"{instance.name} {args.algorithm} {label}")
        plot_sru_loads(selected_eval.sru_loads, run_dir / "sru_loads.png", f"{instance.name} SRU Loads")
        plot_cross_chain_flow(dict(flow), run_dir / "cross_chain_flow.png", f"{instance.name} Cross-Chain Flow")
        if not args.skip_gantt:
            plot_gantt(selected_eval.records, run_dir / "gantt.png", f"{instance.name} Schedule")

    print(f"output_dir: {run_dir.as_posix()}")
    print(f"pareto_points: {(run_dir / 'pareto_points.csv').as_posix()}")
    print(f"summary: {(run_dir / 'summary.json').as_posix()}")
    print(
        f"front_points: {len(rows)} runtime_s: {runtime_s:.3f} "
        f"stop={stop_meta['stop_reason']} iter={stop_meta['iterations_completed']}"
    )


if __name__ == "__main__":
    main()
