from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

try:
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover
    plt = None

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.baselines import NSGAIIConfig, run_nsgaii
from smdfjsp.core.pareto import get_non_dominated_indices
from smdfjsp.core.types import Job, Operation, ProcessOption, SMDFJSPInstance, SRU
from smdfjsp.eda_ts import EDATS, EDATSConfig
from smdfjsp.model.evaluator import evaluate_individual


TYPE_STR_TO_INT = {"T1": 1, "T2": 2, "T3": 3}


def _load_mvc_instance(path: Path) -> SMDFJSPInstance:
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["problem_type"] == "MVC-SM-DFJSP", "Input JSON is not MVC-SM-DFJSP."
    type_ids = [str(t["id"]) for t in data.get("types", [])]
    type_str_to_int = {t: idx for idx, t in enumerate(type_ids, start=1)} or TYPE_STR_TO_INT

    sru_str_to_int: Dict[str, int] = {}
    sru_type_int: Dict[str, int] = {}
    srus: List[SRU] = []
    machine_str_to_int: Dict[str, int] = {}
    machine_cursor = 1

    for sru_idx, s in enumerate(data["srus"], start=1):
        sid = str(s["id"])
        sru_str_to_int[sid] = sru_idx
        t_int = type_str_to_int[str(s["type"])]
        sru_type_int[sid] = t_int
        machine_ids: List[int] = []
        for m in s["machines"]:
            gmid = str(m["global_machine_id"])
            if gmid not in machine_str_to_int:
                machine_str_to_int[gmid] = machine_cursor
                machine_cursor += 1
            machine_ids.append(machine_str_to_int[gmid])
        srus.append(SRU(sru_id=sru_idx, type_id=t_int, machine_ids=machine_ids))

    jobs: List[Job] = []
    transport_time: Dict[Tuple[int, int], int] = {}
    transport_cost_per_time: Dict[Tuple[int, int], float] = {}

    for j in data["jobs"]:
        job_id = int(j["job_id"])
        t_str = str(j["type"])
        t_int = type_str_to_int[t_str]
        candidate_sru_strs = [str(x) for x in j["candidate_srus"]]

        operations: List[Operation] = []
        for op in j["operations"]:
            op_id = int(op["op_id"])
            options: List[ProcessOption] = []
            proc_by_sru = op["processing_options_by_sru"]

            for sru_str in candidate_sru_strs:
                sru_int = sru_str_to_int[sru_str]
                cross_info = data["cross_chain"][f"J{job_id}"][sru_str]
                rate = float(cross_info["cross_chain_cost_rate"])

                for item in proc_by_sru[sru_str]:
                    gmid = str(item["global_machine_id"])
                    machine_id = machine_str_to_int[gmid]
                    pt = int(item["adjusted_processing_time"])
                    base_cp = float(item["unit_processing_cost"])
                    # Include cross-chain variable rate on processing cost.
                    cp = base_cp * (1.0 + rate)
                    options.append(
                        ProcessOption(
                            sru_id=sru_int,
                            machine_id=machine_id,
                            process_time=pt,
                            process_cost_per_time=cp,
                        )
                    )
            operations.append(Operation(op_id=op_id, options=options))

        for sru_str in candidate_sru_strs:
            sru_int = sru_str_to_int[sru_str]
            tt = int(data["transport_time"][f"J{job_id}"][sru_str])
            tc_total = float(data["transport_cost"][f"J{job_id}"][sru_str])
            fixed = float(data["cross_chain"][f"J{job_id}"][sru_str]["cross_chain_fixed_cost"])
            # Evaluator adds (transport_time * transport_cost_per_time).
            # Encode transport total + cross-chain fixed as per-time equivalent.
            cp_t = (tc_total + fixed) / max(tt, 1)
            transport_time[(job_id, sru_int)] = tt
            transport_cost_per_time[(job_id, sru_int)] = cp_t

        jobs.append(Job(job_id=job_id, type_id=t_int, operations=operations))

    meta = {
        "source_schema": "MVC-SM-DFJSP",
        "source_path": str(path.as_posix()),
        "mapping": {
            "sru_str_to_int": sru_str_to_int,
            "machine_str_to_int": machine_str_to_int,
            "type_str_to_int": type_str_to_int,
        },
    }
    return SMDFJSPInstance(
        name=str(data["instance_name"]),
        num_types=int(data.get("n_types", len(type_str_to_int))),
        jobs=jobs,
        srus=srus,
        transport_time=transport_time,
        transport_cost_per_time=transport_cost_per_time,
        metadata=meta,
    )


def _front_rows(algo: str, run_id: int, nd_solutions) -> List[dict]:
    rows: List[dict] = []
    seen = set()
    for sol in nd_solutions:
        if sol.objectives is None:
            continue
        key = (round(float(sol.objectives[0]), 8), round(float(sol.objectives[1]), 8))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "algorithm": algo,
                "run": run_id,
                "cost": float(sol.objectives[0]),
                "makespan": float(sol.objectives[1]),
            }
        )
    return rows


def _solution_candidates(algo: str, run_id: int, nd_solutions) -> List[dict]:
    candidates: List[dict] = []
    for sol in nd_solutions:
        if sol.objectives is None:
            continue
        candidates.append(
            {
                "algorithm": algo,
                "run": run_id,
                "cost": float(sol.objectives[0]),
                "makespan": float(sol.objectives[1]),
                "solution": sol,
            }
        )
    return candidates


def _write_csv(path: Path, rows: List[dict], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _plot(front_rows: List[dict], out_png: Path) -> None:
    if plt is None:
        return
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 6), dpi=160)
    styles = {"EDA-TS": ("#1f77b4", "o"), "NSGA-II": ("#2ca02c", "s"), "GLOBAL-ND": ("#d62728", "^")}
    for name in ["EDA-TS", "NSGA-II", "GLOBAL-ND"]:
        pts = [r for r in front_rows if r["algorithm"] == name]
        if not pts:
            continue
        c, m = styles[name]
        xs = [x["cost"] for x in pts]
        ys = [x["makespan"] for x in pts]
        ax.scatter(xs, ys, s=28, alpha=0.85, c=c, marker=m, label=name)
    ax.set_title("Pareto Front on mk05_mvc_3vc_6sru")
    ax.set_xlabel("Total Cost")
    ax.set_ylabel("Makespan")
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_png)
    plt.close(fig)


def _select_compromise_candidate(candidates: List[dict]) -> dict | None:
    if not candidates:
        return None
    points = [(float(c["cost"]), float(c["makespan"])) for c in candidates]
    nd_idx = get_non_dominated_indices(points)
    nd_candidates = [candidates[i] for i in nd_idx]
    if not nd_candidates:
        return None

    costs = [float(c["cost"]) for c in nd_candidates]
    makespans = [float(c["makespan"]) for c in nd_candidates]
    min_cost, max_cost = min(costs), max(costs)
    min_mk, max_mk = min(makespans), max(makespans)

    def score(c: dict) -> Tuple[float, float, float]:
        cost_span = max(max_cost - min_cost, 1e-9)
        mk_span = max(max_mk - min_mk, 1e-9)
        norm_cost = (float(c["cost"]) - min_cost) / cost_span
        norm_mk = (float(c["makespan"]) - min_mk) / mk_span
        return (norm_cost + norm_mk, float(c["cost"]), float(c["makespan"]))

    return min(nd_candidates, key=score)


def _plot_gantt(inst: SMDFJSPInstance, candidate: dict, out_png: Path) -> None:
    if plt is None:
        return
    ev = evaluate_individual(inst, candidate["solution"])
    if not ev.feasible or not ev.records:
        return

    mapping = inst.metadata.get("mapping", {})
    sru_str_to_int = mapping.get("sru_str_to_int", {}) if isinstance(mapping, dict) else {}
    machine_str_to_int = mapping.get("machine_str_to_int", {}) if isinstance(mapping, dict) else {}
    sru_int_to_str = {int(v): str(k) for k, v in dict(sru_str_to_int).items()}
    machine_int_to_str = {int(v): str(k) for k, v in dict(machine_str_to_int).items()}

    lanes = sorted({(r.sru_id, r.machine_id) for r in ev.records}, key=lambda x: (x[0], x[1]))
    lane_pos = {lane: i for i, lane in enumerate(lanes)}
    cmap = plt.get_cmap("tab20")
    job_ids = sorted({r.job_id for r in ev.records})
    job_color = {jid: cmap(i % 20) for i, jid in enumerate(job_ids)}

    fig_h = max(5.0, 0.42 * len(lanes) + 2.4)
    fig, ax = plt.subplots(figsize=(14, fig_h), dpi=160)
    for r in ev.records:
        y = lane_pos[(r.sru_id, r.machine_id)]
        ax.barh(
            y,
            r.end - r.start,
            left=r.start,
            height=0.72,
            color=job_color[r.job_id],
            edgecolor="black",
            linewidth=0.25,
            alpha=0.9,
        )
        if (r.end - r.start) >= 1.5:
            ax.text(r.start + 0.08, y, f"J{r.job_id}-O{r.op_id}", va="center", ha="left", fontsize=6)

    labels = []
    for sid, mid in lanes:
        sru_label = sru_int_to_str.get(sid, f"S{sid}")
        machine_label = machine_int_to_str.get(mid, f"M{mid}")
        labels.append(f"{sru_label}-{machine_label.split('_')[-1]}")
    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("Time")
    ax.set_ylabel("SRU-Machine")
    ax.set_title(
        "Gantt of selected global-ND compromise solution "
        f"({candidate['algorithm']}, run={candidate['run']}, "
        f"cost={float(candidate['cost']):.2f}, makespan={float(candidate['makespan']):.2f})"
    )
    ax.grid(axis="x", linestyle="--", alpha=0.25)
    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/mvc_sm_dfjsp/mk05_mvc_3vc_6sru.json")
    parser.add_argument("--out-dir", default="reports/mvc_pareto/mk05_mvc_3vc_6sru")
    parser.add_argument("--seed", type=int, default=20260428)
    parser.add_argument("--n-runs", type=int, default=3)
    parser.add_argument("--edats-popsize", type=int, default=50)
    parser.add_argument("--edats-max-iter", type=int, default=60)
    parser.add_argument("--edats-time-limit", type=float, default=40.0)
    parser.add_argument("--nsgaii-popsize", type=int, default=50)
    parser.add_argument("--nsgaii-max-iter", type=int, default=60)
    parser.add_argument("--nsgaii-time-limit", type=float, default=40.0)
    args = parser.parse_args()

    input_path = ROOT / args.input
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    inst = _load_mvc_instance(input_path)

    rows_algo: List[dict] = []
    time_rows: List[dict] = []
    solution_candidates: List[dict] = []

    for run_id in range(1, int(args.n_runs) + 1):
        seed_i = int(args.seed) + run_id

        edats_cfg = EDATSConfig(
            popsize=int(args.edats_popsize),
            max_iter=int(args.edats_max_iter),
            time_limit_s=float(args.edats_time_limit),
            seed=seed_i,
        )
        t0 = time.time()
        edats_res = EDATS(inst, edats_cfg).run()
        t_edats = time.time() - t0
        edats_rows = _front_rows("EDA-TS", run_id, edats_res.nd_solutions)
        rows_algo.extend(edats_rows)
        solution_candidates.extend(_solution_candidates("EDA-TS", run_id, edats_res.nd_solutions))
        time_rows.append({"algorithm": "EDA-TS", "run": run_id, "seed": seed_i, "runtime_s": t_edats, "nd_size": len(edats_rows)})

        nsgaii_cfg = NSGAIIConfig(
            popsize=int(args.nsgaii_popsize),
            max_iter=int(args.nsgaii_max_iter),
            time_limit_s=float(args.nsgaii_time_limit),
            seed=seed_i,
        )
        t0 = time.time()
        nsgaii_res = run_nsgaii(inst, nsgaii_cfg)
        t_nsgaii = time.time() - t0
        nsgaii_rows = _front_rows("NSGA-II", run_id, nsgaii_res.nd_solutions)
        rows_algo.extend(nsgaii_rows)
        solution_candidates.extend(_solution_candidates("NSGA-II", run_id, nsgaii_res.nd_solutions))
        time_rows.append(
            {"algorithm": "NSGA-II", "run": run_id, "seed": seed_i, "runtime_s": t_nsgaii, "nd_size": len(nsgaii_rows)}
        )

        print(
            f"run={run_id} seed={seed_i} | EDA-TS nd={len(edats_rows)} ({t_edats:.2f}s) | "
            f"NSGA-II nd={len(nsgaii_rows)} ({t_nsgaii:.2f}s)"
        )

    points = [(float(r["cost"]), float(r["makespan"])) for r in rows_algo]
    nd_idx = get_non_dominated_indices(points)
    rows_global = []
    seen_global = set()
    for idx in nd_idx:
        key = (round(float(rows_algo[idx]["cost"]), 8), round(float(rows_algo[idx]["makespan"]), 8))
        if key in seen_global:
            continue
        seen_global.add(key)
        rows_global.append(
            {
                "algorithm": "GLOBAL-ND",
                "run": int(rows_algo[idx]["run"]),
                "cost": float(rows_algo[idx]["cost"]),
                "makespan": float(rows_algo[idx]["makespan"]),
            }
        )

    all_rows = rows_algo + rows_global
    _write_csv(
        out_dir / "pareto_points.csv",
        all_rows,
        ["algorithm", "run", "cost", "makespan"],
    )
    _write_csv(
        out_dir / "runtime_summary.csv",
        time_rows,
        ["algorithm", "run", "seed", "runtime_s", "nd_size"],
    )
    (out_dir / "runtime_summary.json").write_text(
        json.dumps(
            {
                "input": str(input_path.as_posix()),
                "n_runs": int(args.n_runs),
                "seed_base": int(args.seed),
                "rows": time_rows,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    _plot(all_rows, out_dir / "pareto_nsga2_edats.png")
    plot_path = out_dir / "pareto_nsga2_edats.png"
    selected = _select_compromise_candidate(solution_candidates)
    gantt_path = out_dir / "gantt_selected_compromise.png"
    if selected is not None:
        _plot_gantt(inst, selected, gantt_path)
        selected_payload = {
            "selection_rule": "global non-dominated solution with minimum normalized(cost)+normalized(makespan)",
            "algorithm": selected["algorithm"],
            "run": int(selected["run"]),
            "cost": float(selected["cost"]),
            "makespan": float(selected["makespan"]),
        }
        (out_dir / "selected_compromise_solution.json").write_text(
            json.dumps(selected_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    print(f"output_dir: {out_dir.as_posix()}")
    print(f"pareto_points: {(out_dir / 'pareto_points.csv').as_posix()}")
    if plot_path.exists():
        print(f"plot: {plot_path.as_posix()}")
    else:
        print("plot: not generated (matplotlib is not available in current Python environment)")
    if gantt_path.exists():
        print(f"gantt: {gantt_path.as_posix()}")
    else:
        print("gantt: not generated (matplotlib unavailable or no feasible selected solution)")


if __name__ == "__main__":
    main()
