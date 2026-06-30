from __future__ import annotations

import argparse
import csv
import itertools
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from mvc_experiment_utils import front_rows, stop_metadata, write_csv
from smdfjsp.core.encoding import build_option_index, op_from_ua_os
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.types import EncodedIndividual, ScheduleRecord
from smdfjsp.data.mvc_io import get_candidate_srus, load_mvc_instance_json
from smdfjsp.metrics.multiobjective import auto_reference_point, normalized_hypervolume, objective_bounds, igd, raw_igd
from smdfjsp.model.mvc_evaluator import evaluate_mvc_individual
from smdfjsp.mvc_eda_ts import MVCEDATS, MVCEDATSConfig


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _sru_label(sru_id: int) -> str:
    return f"U{sru_id}"


def _job_label(job_id: int) -> str:
    return f"J{job_id}"


def _machine_label(sru_id: int, local_machine_id: int) -> str:
    return f"U{sru_id}_M{local_machine_id}"


def _job_payload(
    job_id: int,
    value_chain: str,
    type_label: str,
    operations: Sequence[Mapping[int, Sequence[tuple[int, float]]]],
    candidate_srus: Sequence[int],
) -> dict:
    raw_ops = []
    for op_idx, by_sru in enumerate(operations, start=1):
        by_sru_payload: dict[str, list[dict]] = {}
        for sru_id, machine_options in by_sru.items():
            by_sru_payload[_sru_label(sru_id)] = [
                {
                    "global_machine_id": _machine_label(sru_id, machine_id),
                    "local_machine_id": f"M{machine_id}",
                    "base_machine_id": machine_id,
                    "base_processing_time": process_time,
                    "adjusted_processing_time": process_time,
                    "unit_processing_cost": unit_cost,
                }
                for machine_id, process_time, unit_cost in machine_options
            ]
        raw_ops.append(
            {
                "op_id": op_idx,
                "op_id_zero_based": op_idx - 1,
                "processing_options_by_sru": by_sru_payload,
            }
        )
    return {
        "job_id": job_id,
        "job_id_zero_based": job_id - 1,
        "value_chain": value_chain,
        "type": type_label,
        "release_time": 0,
        "n_operations": len(operations),
        "candidate_srus": [_sru_label(x) for x in candidate_srus],
        "operations": raw_ops,
    }


def _payload(
    instance_name: str,
    jobs: Sequence[dict],
    transport_time: Mapping[tuple[int, int], float],
    transport_cost: Mapping[tuple[int, int], float],
    cross_fixed_cost: Mapping[tuple[int, int], float],
) -> dict:
    srus = [
        {"id": "U1", "value_chain": "VC1", "type": "T1", "open_to_cross_chain": True, "machines": [{"global_machine_id": "U1_M1"}, {"global_machine_id": "U1_M2"}]},
        {"id": "U2", "value_chain": "VC1", "type": "T2", "open_to_cross_chain": True, "machines": [{"global_machine_id": "U2_M1"}, {"global_machine_id": "U2_M2"}]},
        {"id": "U3", "value_chain": "VC2", "type": "T1", "open_to_cross_chain": True, "machines": [{"global_machine_id": "U3_M1"}, {"global_machine_id": "U3_M2"}]},
        {"id": "U4", "value_chain": "VC2", "type": "T2", "open_to_cross_chain": True, "machines": [{"global_machine_id": "U4_M1"}, {"global_machine_id": "U4_M2"}]},
    ]
    all_keys = sorted(set(transport_time) | set(transport_cost) | set(cross_fixed_cost))
    transport_time_raw: dict[str, dict[str, float]] = defaultdict(dict)
    transport_cost_raw: dict[str, dict[str, float]] = defaultdict(dict)
    cross_raw: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    job_vc = {int(j["job_id"]): str(j["value_chain"]) for j in jobs}
    sru_vc = {idx: str(raw["value_chain"]) for idx, raw in enumerate(srus, start=1)}
    for job_id, sru_id in all_keys:
        j_label = _job_label(job_id)
        u_label = _sru_label(sru_id)
        transport_time_raw[j_label][u_label] = float(transport_time.get((job_id, sru_id), 0.0))
        transport_cost_raw[j_label][u_label] = float(transport_cost.get((job_id, sru_id), 0.0))
        is_cross = job_vc[job_id] != sru_vc[sru_id]
        cross_raw[j_label][u_label] = {
            "is_cross_chain": is_cross,
            "cross_chain_fixed_cost": float(cross_fixed_cost.get((job_id, sru_id), 0.0)),
            "cross_chain_cost_rate": 0.0,
            "job_value_chain": job_vc[job_id],
            "sru_value_chain": sru_vc[sru_id],
        }
    return {
        "instance_name": instance_name,
        "source_instance": instance_name,
        "problem_type": "MVC-SM-DFJSP",
        "is_dynamic": False,
        "release_time_policy": "all_zero",
        "n_jobs": len(jobs),
        "n_value_chains": 2,
        "n_types": 2,
        "n_srus": 4,
        "value_chains": [
            {"id": "VC1", "name": "Value chain 1", "jobs": [j["job_id"] for j in jobs if j["value_chain"] == "VC1"]},
            {"id": "VC2", "name": "Value chain 2", "jobs": [j["job_id"] for j in jobs if j["value_chain"] == "VC2"]},
        ],
        "types": [
            {"id": "T1", "name": "Service type 1", "jobs": [j["job_id"] for j in jobs if j["type"] == "T1"]},
            {"id": "T2", "name": "Service type 2", "jobs": [j["job_id"] for j in jobs if j["type"] == "T2"]},
        ],
        "srus": srus,
        "jobs": list(jobs),
        "transport_time": transport_time_raw,
        "transport_cost": transport_cost_raw,
        "cross_chain": cross_raw,
        "objectives": [
            {"id": "total_cost", "sense": "min", "definition": "PC + TC + CFC"},
            {"id": "makespan", "sense": "min", "definition": "max(C_j + transport_time)"},
        ],
    }


def build_small_payloads() -> list[dict]:
    small_01_jobs = [
        _job_payload(1, "VC1", "T1", [{1: [(1, 3, 2.0)], 3: [(1, 2, 3.0)]}, {1: [(1, 2, 2.0)], 3: [(1, 4, 3.0)]}], [1, 3]),
        _job_payload(2, "VC2", "T1", [{1: [(1, 5, 2.0)], 3: [(1, 3, 2.5)]}], [1, 3]),
        _job_payload(3, "VC1", "T2", [{2: [(1, 4, 1.5)], 4: [(1, 2, 2.5)]}, {2: [(1, 3, 1.5)], 4: [(1, 5, 2.5)]}], [2, 4]),
    ]
    small_02_jobs = [
        _job_payload(1, "VC1", "T1", [{1: [(1, 4, 2.0), (2, 5, 1.5)], 3: [(1, 3, 3.0), (2, 4, 2.5)]}, {1: [(1, 3, 2.0), (2, 2, 2.8)], 3: [(1, 4, 3.0), (2, 3, 2.5)]}], [1, 3]),
        _job_payload(2, "VC2", "T1", [{1: [(1, 5, 2.0), (2, 4, 2.2)], 3: [(1, 3, 2.4), (2, 5, 1.8)]}, {1: [(1, 2, 2.0), (2, 3, 1.7)], 3: [(1, 4, 2.4), (2, 2, 2.1)]}], [1, 3]),
        _job_payload(3, "VC1", "T2", [{2: [(1, 3, 1.8), (2, 4, 1.4)], 4: [(1, 2, 2.6), (2, 3, 2.0)]}, {2: [(1, 4, 1.8), (2, 2, 2.3)], 4: [(1, 5, 2.6), (2, 4, 2.0)]}], [2, 4]),
        _job_payload(4, "VC2", "T2", [{2: [(1, 4, 1.8), (2, 5, 1.4)], 4: [(1, 3, 2.0), (2, 4, 1.7)]}, {2: [(1, 3, 1.8), (2, 4, 1.4)], 4: [(1, 2, 2.0), (2, 3, 1.7)]}], [2, 4]),
    ]
    small_03_jobs = [
        _job_payload(1, "VC1", "T1", [{1: [(1, 5, 2.0), (2, 6, 1.5)], 3: [(1, 3, 3.2), (2, 4, 2.4)]}, {1: [(1, 4, 2.0), (2, 3, 2.6)], 3: [(1, 5, 3.2), (2, 3, 2.4)]}], [1, 3]),
        _job_payload(2, "VC1", "T1", [{1: [(1, 6, 1.7)], 3: [(1, 4, 2.7)]}], [1, 3]),
        _job_payload(3, "VC2", "T1", [{1: [(1, 6, 1.7)], 3: [(1, 4, 2.1)]}], [1, 3]),
        _job_payload(4, "VC1", "T2", [{2: [(1, 4, 1.6), (2, 5, 1.2)], 4: [(1, 2, 2.8), (2, 3, 2.2)]}], [2, 4]),
        _job_payload(5, "VC2", "T2", [{2: [(1, 5, 1.6)], 4: [(1, 3, 2.0)]}], [2, 4]),
    ]

    def costs(jobs: Sequence[dict]) -> tuple[dict[tuple[int, int], float], dict[tuple[int, int], float], dict[tuple[int, int], float]]:
        t_time: dict[tuple[int, int], float] = {}
        t_cost: dict[tuple[int, int], float] = {}
        fixed: dict[tuple[int, int], float] = {}
        sru_vc = {1: "VC1", 2: "VC1", 3: "VC2", 4: "VC2"}
        for job in jobs:
            job_id = int(job["job_id"])
            for raw_sru in job["candidate_srus"]:
                sru_id = int(str(raw_sru).replace("U", ""))
                cross = str(job["value_chain"]) != sru_vc[sru_id]
                t_time[(job_id, sru_id)] = 1.0 if not cross else 2.0
                t_cost[(job_id, sru_id)] = 3.0 if not cross else 7.0
                fixed[(job_id, sru_id)] = 0.0 if not cross else 10.0
        return t_time, t_cost, fixed

    payloads = []
    for name, jobs in [
        ("mvc_small_01", small_01_jobs),
        ("mvc_small_02", small_02_jobs),
        ("mvc_small_03", small_03_jobs),
    ]:
        transport_time, transport_cost, cross_fixed_cost = costs(jobs)
        payloads.append(_payload(name, jobs, transport_time, transport_cost, cross_fixed_cost))
    return payloads


def write_small_instances(data_dir: Path) -> list[Path]:
    data_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for payload in build_small_payloads():
        path = data_dir / f"{payload['instance_name']}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        paths.append(path)
    return paths


def _unique_permutations(items: Sequence[int]) -> Iterable[tuple[int, ...]]:
    counter = Counter(items)
    n = len(items)

    def visit(prefix: list[int]) -> Iterable[tuple[int, ...]]:
        if len(prefix) == n:
            yield tuple(prefix)
            return
        for value in sorted(counter):
            if counter[value] <= 0:
                continue
            counter[value] -= 1
            prefix.append(value)
            yield from visit(prefix)
            prefix.pop()
            counter[value] += 1

    yield from visit([])


def _os_permutations(instance: MVCSMDFJSPInstance) -> Iterable[dict[int, list[int]]]:
    per_type: list[tuple[int, list[tuple[int, ...]]]] = []
    for type_id in range(1, instance.num_types + 1):
        tokens: list[int] = []
        for job in instance.jobs:
            if job.type_id == type_id:
                tokens.extend([job.job_id] * len(job.operations))
        per_type.append((type_id, list(_unique_permutations(tokens))))
    for combo in itertools.product(*(x[1] for x in per_type)):
        yield {type_id: list(seq) for (type_id, _), seq in zip(per_type, combo)}


def _ua_assignments(instance: MVCSMDFJSPInstance, mode: MVCModeConfig) -> Iterable[dict[int, int]]:
    jobs = sorted(instance.jobs, key=lambda j: j.job_id)
    choices = [get_candidate_srus(job, instance, mode) for job in jobs]
    for combo in itertools.product(*choices):
        yield {job.job_id: int(sru_id) for job, sru_id in zip(jobs, combo)}


def _machine_assignments(
    instance: MVCSMDFJSPInstance,
    option_index: Mapping[tuple[int, int, int], Mapping[int, tuple[float, float]]],
    op_layer: Mapping[int, Sequence[tuple[int, int]]],
) -> Iterable[dict[int, list[int]]]:
    srus = sorted(s.sru_id for s in instance.srus)
    choice_lists: list[list[int]] = []
    positions: list[tuple[int, int]] = []
    for sru_id in srus:
        for idx, (job_id, op_id) in enumerate(op_layer.get(sru_id, [])):
            choices = sorted(option_index[(job_id, op_id, sru_id)])
            choice_lists.append(choices)
            positions.append((sru_id, idx))
    if not choice_lists:
        yield {sru_id: [] for sru_id in srus}
        return
    for combo in itertools.product(*choice_lists):
        out = {sru_id: [0] * len(op_layer.get(sru_id, [])) for sru_id in srus}
        for (sru_id, idx), machine_id in zip(positions, combo):
            out[sru_id][idx] = int(machine_id)
        yield out


def _objective_key(values: Sequence[float], digits: int = 8) -> tuple[float, ...]:
    return tuple(round(float(x), digits) for x in values)


def _filter_exact_front(rows: Sequence[dict]) -> list[dict]:
    front: list[dict] = []
    for row in rows:
        obj = (float(row["total_cost"]), float(row["makespan"]))
        dominated = False
        for other in rows:
            other_obj = (float(other["total_cost"]), float(other["makespan"]))
            if other_obj == obj:
                continue
            if other_obj[0] <= obj[0] and other_obj[1] <= obj[1] and (other_obj[0] < obj[0] or other_obj[1] < obj[1]):
                dominated = True
                break
        if not dominated:
            front.append(dict(row))
    seen = set()
    unique = []
    for row in sorted(front, key=lambda r: (float(r["total_cost"]), float(r["makespan"]))):
        key = _objective_key((float(row["total_cost"]), float(row["makespan"])))
        if key in seen:
            continue
        seen.add(key)
        row = dict(row)
        row["exact_solution_id"] = len(unique) + 1
        unique.append(row)
    return unique


def exact_enumeration(instance: MVCSMDFJSPInstance, mode: MVCModeConfig, max_evaluations: int | None = None) -> tuple[list[dict], list[EncodedIndividual], int, int]:
    option_index = build_option_index(instance)  # type: ignore[arg-type]
    all_rows: list[dict] = []
    representatives: dict[tuple[float, ...], EncodedIndividual] = {}
    evaluations = 0
    infeasible = 0
    mode_label = "on" if mode.cross_chain_allowed else "off"
    for ua in _ua_assignments(instance, mode):
        for os_layer in _os_permutations(instance):
            op_layer = op_from_ua_os(instance, ua, os_layer)  # type: ignore[arg-type]
            for ms_layer in _machine_assignments(instance, option_index, op_layer):
                evaluations += 1
                if max_evaluations is not None and evaluations > max_evaluations:
                    raise RuntimeError(f"Exact enumeration exceeded --max-exact-evaluations={max_evaluations}")
                ind = EncodedIndividual(ua=dict(ua), os={k: list(v) for k, v in os_layer.items()}, op={k: list(v) for k, v in op_layer.items()}, ms=ms_layer)
                ev = evaluate_mvc_individual(instance, ind, mode)
                if not ev.feasible:
                    infeasible += 1
                    continue
                key = _objective_key(ev.objectives)
                representatives.setdefault(key, ind)
                all_rows.append(
                    {
                        "instance": instance.name,
                        "cross_chain": mode_label,
                        "total_cost": ev.total_cost,
                        "makespan": ev.makespan,
                        "processing_cost": ev.cost_breakdown.get("processing_cost", 0.0),
                        "transport_cost": ev.cost_breakdown.get("transport_cost", 0.0),
                        "cross_fixed_cost": ev.cost_breakdown.get("cross_fixed_cost", 0.0),
                        "cross_chain_jobs": ev.diagnostics.get("cross_chain_jobs", 0),
                        "cross_chain_ratio": ev.diagnostics.get("cross_chain_ratio", 0.0),
                        "ua": json.dumps(ind.ua, ensure_ascii=False, sort_keys=True),
                        "os": json.dumps(ind.os, ensure_ascii=False, sort_keys=True),
                        "ms": json.dumps(ind.ms, ensure_ascii=False, sort_keys=True),
                    }
                )
    front_rows = _filter_exact_front(all_rows)
    front_solutions = [representatives[_objective_key((row["total_cost"], row["makespan"]))] for row in front_rows]
    return front_rows, front_solutions, evaluations, infeasible


def _run_algorithm(instance: MVCSMDFJSPInstance, mode: MVCModeConfig, args: argparse.Namespace) -> tuple[list[dict], int]:
    all_rows: list[dict] = []
    infeasible_count = 0
    cross_label = "on" if mode.cross_chain_allowed else "off"
    for seed in args.seeds:
        cfg = MVCEDATSConfig(
            popsize=args.popsize,
            max_iter=args.max_iter,
            time_limit_s=args.time_limit,
            seed=int(seed),
            local_search_steps=args.local_search_steps,
        )
        result = MVCEDATS(instance, cfg, mode).run()
        meta = {
            "instance": instance.name,
            "algorithm": "mvc-edats",
            "cross_chain": cross_label,
            "seed": int(seed),
            "objective_dim": 2,
            "runtime_s": float(result.elapsed_s),
        }
        meta.update(stop_metadata(result, result.elapsed_s))
        rows, _details = front_rows(instance, result.nd_solutions, mode, meta)
        feasible_ids = {int(row["solution_id"]) for row in rows}
        infeasible_count += max(0, len(result.nd_solutions) - len(feasible_ids))
        all_rows.extend(rows)
    return all_rows, infeasible_count


def _compare_fronts(exact_rows: Sequence[dict], algorithm_rows: Sequence[dict], infeasible_count: int) -> dict:
    exact_objs = [_objective_key((r["total_cost"], r["makespan"])) for r in exact_rows]
    algorithm_objs = [_objective_key((r["total_cost"], r["makespan"])) for r in algorithm_rows]
    exact_set = set(exact_objs)
    algorithm_set = set(algorithm_objs)
    found = exact_set & algorithm_set
    false_nd = [obj for obj in algorithm_set if obj not in exact_set]
    exact_front = [tuple(map(float, obj)) for obj in exact_set]
    algorithm_front = [tuple(map(float, obj)) for obj in algorithm_set]
    if exact_front and algorithm_front:
        fronts = [exact_front, algorithm_front]
        ref = auto_reference_point(fronts)
        lower_bounds, upper_bounds = objective_bounds(fronts)
        hv_gap = normalized_hypervolume(exact_front, ref, lower_bounds, upper_bounds) - normalized_hypervolume(
            algorithm_front,
            ref,
            lower_bounds,
            upper_bounds,
        )
        exact_igd = igd(algorithm_front, exact_front, lower_bounds, upper_bounds)
        raw_exact_igd = raw_igd(algorithm_front, exact_front)
    elif exact_front:
        fronts = [exact_front]
        ref = auto_reference_point(fronts)
        lower_bounds, upper_bounds = objective_bounds(fronts)
        hv_gap = normalized_hypervolume(exact_front, ref, lower_bounds, upper_bounds)
        exact_igd = float("inf")
        raw_exact_igd = float("inf")
    else:
        hv_gap = 0.0
        exact_igd = 0.0
        raw_exact_igd = 0.0
    return {
        "exact_front_size": len(exact_set),
        "algorithm_front_size": len(algorithm_set),
        "exact_coverage": len(found) / max(len(exact_set), 1),
        "false_nd_count": len(false_nd),
        "infeasible_count": infeasible_count,
        "exact_hv_gap": hv_gap,
        "exact_igd": exact_igd,
        "raw_exact_igd": raw_exact_igd,
    }


def _audit_solution(instance: MVCSMDFJSPInstance, mode: MVCModeConfig, ind: EncodedIndividual) -> tuple[list[dict], list[dict]]:
    ev = evaluate_mvc_individual(instance, ind, mode)
    job_map = instance.job_map()
    sru_map = instance.sru_map()
    cost_rows = []
    for job_id, sru_id in sorted(ind.ua.items()):
        job_records = [r for r in ev.records if r.job_id == job_id]
        processing_cost = 0.0
        for rec in job_records:
            job = job_map[rec.job_id]
            op = job.operations[rec.op_id - 1]
            opt = next(x for x in op.options if x.sru_id == rec.sru_id and x.machine_id == rec.machine_id)
            processing_cost += float(opt.process_time) * float(opt.process_cost_per_time)
        cost_rows.append(
            {
                "instance": instance.name,
                "cross_chain": "on" if mode.cross_chain_allowed else "off",
                "job_id": job_id,
                "sru_id": sru_id,
                "job_value_chain": job_map[job_id].value_chain_id,
                "sru_value_chain": sru_map[sru_id].value_chain_id,
                "is_cross_chain": bool(instance.is_cross_chain.get((job_id, sru_id), False)),
                "processing_cost": processing_cost,
                "transport_cost": instance.transport_cost[(job_id, sru_id)],
                "cross_fixed_cost": instance.cross_chain_fixed_cost[(job_id, sru_id)],
                "job_completion": max((r.end for r in job_records), default=0.0),
                "transport_time": instance.transport_time[(job_id, sru_id)],
            }
        )

    schedule_rows = []
    by_machine: dict[tuple[int, int], list[ScheduleRecord]] = defaultdict(list)
    by_job: dict[int, list[ScheduleRecord]] = defaultdict(list)
    for rec in ev.records:
        by_machine[(rec.sru_id, rec.machine_id)].append(rec)
        by_job[rec.job_id].append(rec)
    machine_ok = True
    for records in by_machine.values():
        ordered = sorted(records, key=lambda x: (x.start, x.end))
        for left, right in zip(ordered, ordered[1:]):
            if left.end > right.start + 1e-9:
                machine_ok = False
    precedence_ok = True
    for records in by_job.values():
        ordered = sorted(records, key=lambda x: x.op_id)
        for left, right in zip(ordered, ordered[1:]):
            if left.end > right.start + 1e-9:
                precedence_ok = False
    for rec in sorted(ev.records, key=lambda x: (x.sru_id, x.machine_id, x.start, x.end)):
        schedule_rows.append(
            {
                "instance": instance.name,
                "cross_chain": "on" if mode.cross_chain_allowed else "off",
                "job_id": rec.job_id,
                "op_id": rec.op_id,
                "sru_id": rec.sru_id,
                "machine_id": rec.machine_id,
                "start": rec.start,
                "end": rec.end,
                "machine_no_overlap_global": machine_ok,
                "precedence_ok_global": precedence_ok,
                "total_cost": ev.total_cost,
                "makespan": ev.makespan,
            }
        )
    return cost_rows, schedule_rows


def _write_markdown(out_dir: Path, summary_rows: Sequence[Mapping[str, object]]) -> None:
    lines = [
        "# MVC-SM-DFJSP Small-Scale Exact Validation",
        "",
        "This report is generated by `scripts/run_mvc_small_exact_validation.py`.",
        "",
        "| Instance | Cross | Exact front | Algorithm front | Coverage | False ND | Infeasible | HV gap | IGD | Raw IGD |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in summary_rows:
        lines.append(
            "| {instance} | {cross_chain} | {exact_front_size} | {algorithm_front_size} | {exact_coverage:.4g} | {false_nd_count} | {infeasible_count} | {exact_hv_gap:.6g} | {exact_igd:.6g} | {raw_exact_igd:.6g} |".format(
                **row
            )
        )
    (out_dir / "validation_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run small-scale exact validation for MVC-SM-DFJSP.")
    parser.add_argument("--data-dir", default="data/mvc_small_validation")
    parser.add_argument("--out-dir", default="reports/mvc_small_validation")
    parser.add_argument("--cross-modes", default="off,on", help="Comma-separated: off,on")
    parser.add_argument("--seeds", default="20260428,20260429,20260430")
    parser.add_argument("--popsize", type=int, default=40)
    parser.add_argument("--max-iter", type=int, default=80)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument("--local-search-steps", type=int, default=6)
    parser.add_argument("--max-exact-evaluations", type=int, default=1_000_000)
    parser.add_argument("--skip-algorithm", action="store_true", help="Only enumerate exact fronts and audits.")
    args = parser.parse_args()
    args.seeds = [int(x.strip()) for x in str(args.seeds).split(",") if x.strip()]

    data_dir = _resolve(args.data_dir)
    out_dir = _resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    instance_paths = write_small_instances(data_dir)

    exact_front_all: list[dict] = []
    algorithm_front_all: list[dict] = []
    summary_rows: list[dict] = []
    cost_audit_rows: list[dict] = []
    schedule_audit_rows: list[dict] = []
    modes = [x.strip() for x in str(args.cross_modes).split(",") if x.strip()]

    for path in instance_paths:
        instance = load_mvc_instance_json(path)
        for mode_name in modes:
            mode = MVCModeConfig(cross_chain_allowed=mode_name == "on", objective_dim=2)
            exact_rows, exact_solutions, exact_evaluations, exact_infeasible = exact_enumeration(
                instance,
                mode,
                max_evaluations=args.max_exact_evaluations,
            )
            exact_front_all.extend(exact_rows)
            algorithm_rows: list[dict] = []
            algorithm_infeasible = 0
            if not args.skip_algorithm:
                algorithm_rows, algorithm_infeasible = _run_algorithm(instance, mode, args)
                algorithm_front_all.extend(algorithm_rows)
            comparison = _compare_fronts(exact_rows, algorithm_rows, algorithm_infeasible)
            summary_rows.append(
                {
                    "instance": instance.name,
                    "cross_chain": mode_name,
                    "exact_evaluations": exact_evaluations,
                    "exact_infeasible_count": exact_infeasible,
                    **comparison,
                }
            )
            if exact_solutions:
                cost_rows, schedule_rows = _audit_solution(instance, mode, exact_solutions[0])
                cost_audit_rows.extend(cost_rows)
                schedule_audit_rows.extend(schedule_rows)

    write_csv(out_dir / "exact_front.csv", exact_front_all)
    write_csv(out_dir / "algorithm_front.csv", algorithm_front_all)
    write_csv(out_dir / "validation_summary.csv", summary_rows)
    write_csv(out_dir / "cost_audit.csv", cost_audit_rows)
    write_csv(out_dir / "schedule_audit.csv", schedule_audit_rows)
    _write_markdown(out_dir, summary_rows)
    (out_dir / "run_meta.json").write_text(json.dumps(vars(args), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"data_dir: {data_dir.as_posix()}")
    print(f"out_dir: {out_dir.as_posix()}")
    print(f"summary: {(out_dir / 'validation_summary.csv').as_posix()}")


if __name__ == "__main__":
    main()
