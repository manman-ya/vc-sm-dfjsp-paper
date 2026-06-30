from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import pstdev
from typing import Dict, List, Tuple

from smdfjsp.core.encoding import build_option_index, op_from_ua_os
from smdfjsp.core.mvc_types import MVCEvalResult, MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.types import EncodedIndividual, ScheduleRecord
from smdfjsp.data.mvc_io import get_candidate_srus
from smdfjsp.model.evaluator import validate_os


@dataclass
class EvaluationTracker:
    """Count objective-function evaluations and enforce an optional budget."""

    max_evaluations: int | None = None
    evaluations: int = 0

    @property
    def remaining(self) -> int | None:
        if self.max_evaluations is None:
            return None
        return max(0, int(self.max_evaluations) - int(self.evaluations))

    @property
    def exhausted(self) -> bool:
        return self.max_evaluations is not None and self.evaluations >= self.max_evaluations

    def consume(self) -> None:
        if self.exhausted:
            raise RuntimeError("objective-function evaluation budget exhausted")
        self.evaluations += 1


def _infinite_result(message: str, objective_dim: int) -> MVCEvalResult:
    objectives = (float("inf"), float("inf"))
    return MVCEvalResult(
        objectives=objectives,
        feasible=False,
        records=[],
        total_cost=float("inf"),
        makespan=float("inf"),
        max_sru_load=float("inf"),
        message=message,
    )


def evaluate_mvc_individual(
    instance: MVCSMDFJSPInstance,
    individual: EncodedIndividual,
    mode: MVCModeConfig | None = None,
    tracker: EvaluationTracker | None = None,
) -> MVCEvalResult:
    if tracker is not None:
        tracker.consume()
    mode = mode or MVCModeConfig()
    if not validate_os(instance, individual.os):  # type: ignore[arg-type]
        return _infinite_result("invalid OS multiset", mode.objective_dim)

    option_index = build_option_index(instance)  # type: ignore[arg-type]
    job_map = instance.job_map()
    sru_map = instance.sru_map()

    for job in instance.jobs:
        sid = individual.ua.get(job.job_id)
        if sid is None:
            return _infinite_result(f"missing UA for job {job.job_id}", mode.objective_dim)
        if sid not in sru_map:
            return _infinite_result(f"unknown SRU {sid}", mode.objective_dim)
        if sid not in get_candidate_srus(job, instance, mode):
            return _infinite_result("cross-chain forbidden or type mismatch", mode.objective_dim)

    if not individual.op:
        individual.op = op_from_ua_os(instance, individual.ua, individual.os)  # type: ignore[arg-type]

    machine_ready: Dict[Tuple[int, int], float] = {}
    job_ready: Dict[int, float] = {j.job_id: float(j.release_time) for j in instance.jobs}
    job_processing_cost: Dict[int, float] = {j.job_id: 0.0 for j in instance.jobs}
    sru_loads: Dict[int, float] = {s.sru_id: 0.0 for s in instance.srus}
    records: List[ScheduleRecord] = []
    processing_cost = 0.0

    for sru_id, seq in individual.op.items():
        ms_vec = individual.ms.get(sru_id, [])
        for idx, (job_id, op_id) in enumerate(seq):
            key = (job_id, op_id, sru_id)
            if key not in option_index:
                return _infinite_result("operation cannot be processed by assigned SRU", mode.objective_dim)
            options = option_index[key]
            machine_id = ms_vec[idx] if idx < len(ms_vec) else None
            if machine_id not in options:
                machine_id = min(options.keys(), key=lambda m: options[m][0])
            pt, cp = options[machine_id]
            start = max(job_ready[job_id], machine_ready.get((sru_id, machine_id), 0.0))
            end = start + float(pt)
            op_cost = float(pt) * float(cp)
            job_ready[job_id] = end
            machine_ready[(sru_id, machine_id)] = end
            job_processing_cost[job_id] += op_cost
            processing_cost += op_cost
            sru_loads[sru_id] = sru_loads.get(sru_id, 0.0) + float(pt)
            records.append(
                ScheduleRecord(
                    job_id=job_id,
                    op_id=op_id,
                    sru_id=sru_id,
                    machine_id=int(machine_id),
                    start=float(start),
                    end=float(end),
                )
            )

    transport_cost = 0.0
    cross_fixed_cost = 0.0
    cross_variable_cost = 0.0
    makespan = 0.0
    cross_count = 0
    flow: Dict[Tuple[str, str], int] = {}
    inflow: Dict[str, int] = {}
    outflow: Dict[str, int] = {}

    for job_id, complete_time in job_ready.items():
        sid = individual.ua[job_id]
        key = (job_id, sid)
        if key not in instance.transport_time or key not in instance.transport_cost:
            return _infinite_result("transport miss", mode.objective_dim)
        job = job_map[job_id]
        sru = sru_map[sid]
        transport_cost += float(instance.transport_cost[key])
        makespan = max(makespan, float(complete_time) + float(instance.transport_time[key]))
        if instance.is_cross_chain.get(key, job.value_chain_id != sru.value_chain_id):
            cross_count += 1
            cross_fixed_cost += float(instance.cross_chain_fixed_cost.get(key, 0.0))
            flow_key = (job.value_chain_id, sru.value_chain_id)
            flow[flow_key] = flow.get(flow_key, 0) + 1
            outflow[job.value_chain_id] = outflow.get(job.value_chain_id, 0) + 1
            inflow[sru.value_chain_id] = inflow.get(sru.value_chain_id, 0) + 1

    total_cost = processing_cost + transport_cost + cross_fixed_cost
    max_sru_load = max(sru_loads.values()) if sru_loads else 0.0
    load_values = [sru_loads.get(s.sru_id, 0.0) for s in instance.srus]
    sru_load_std = float(pstdev(load_values)) if len(load_values) > 1 else 0.0

    vc_loads: Dict[str, float] = {}
    for sid, load in sru_loads.items():
        vc = sru_map[sid].value_chain_id
        vc_loads[vc] = vc_loads.get(vc, 0.0) + load
    vc_load_std = float(pstdev(list(vc_loads.values()))) if len(vc_loads) > 1 else 0.0

    objectives = (float(total_cost), float(makespan))

    if not all(math.isfinite(x) for x in objectives):
        return _infinite_result("non-finite objectives", mode.objective_dim)

    return MVCEvalResult(
        objectives=objectives,
        feasible=True,
        records=records,
        total_cost=float(total_cost),
        makespan=float(makespan),
        max_sru_load=float(max_sru_load),
        cost_breakdown={
            "processing_cost": float(processing_cost),
            "transport_cost": float(transport_cost),
            "cross_fixed_cost": float(cross_fixed_cost),
            # Kept as a compatibility column for historical result CSVs; the
            # formal two-objective model uses fixed cross-chain cost only.
            "cross_variable_cost": float(cross_variable_cost),
            "total_cost": float(total_cost),
        },
        sru_loads={int(k): float(v) for k, v in sru_loads.items()},
        diagnostics={
            "cross_chain_jobs": int(cross_count),
            "cross_chain_ratio": float(cross_count / max(len(instance.jobs), 1)),
            "intra_chain_jobs": int(len(instance.jobs) - cross_count),
            "sru_load_std": sru_load_std,
            "value_chain_load_std": vc_load_std,
            "cross_chain_flow": {f"{a}->{b}": n for (a, b), n in flow.items()},
            "value_chain_inflow": inflow,
            "value_chain_outflow": outflow,
        },
    )


def evaluate_mvc_population(
    instance: MVCSMDFJSPInstance,
    pop: List[EncodedIndividual],
    mode: MVCModeConfig,
    tracker: EvaluationTracker | None = None,
) -> None:
    for ind in pop:
        result = evaluate_mvc_individual(instance, ind, mode, tracker)
        ind.objectives = result.objectives  # type: ignore[assignment]
        ind.feasible = result.feasible
        ind.aux["mvc_eval"] = result
