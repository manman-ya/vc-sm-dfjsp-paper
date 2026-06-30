from __future__ import annotations

import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Tuple

from smdfjsp.core.encoding import op_from_ua_os
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import make_rng
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.metrics.multiobjective import crowding_distance, fast_non_dominated_sort, merge_non_dominated
from smdfjsp.model.mvc_evaluator import EvaluationTracker, evaluate_mvc_population
from smdfjsp.model.mvc_repair import build_mvc_compatible_sru_map, build_random_mvc_individual, repair_mvc_individual


@dataclass
class MVCNSGAIIConfig:
    popsize: int = 50
    max_iter: int = 100
    time_limit_s: float = 100.0
    cr: float = 0.7
    mr: float = 0.3
    seed: int = 42
    nd_pool_max: int = 300
    max_evaluations: int | None = None
    time_measure: str = "wall"


@dataclass
class MVCRunResult:
    nd_solutions: List[EncodedIndividual]
    history: List[Dict[str, float]]
    stop_reason: str = ""
    iterations_completed: int = 0
    elapsed_s: float = 0.0
    evaluations_completed: int = 0
    phase_times: Dict[str, float] | None = None
    budget_elapsed_s: float = 0.0
    time_measure: str = "wall"


def _rank_and_crowding(pop: List[EncodedIndividual]) -> Tuple[Dict[int, int], Dict[int, float]]:
    objs = [tuple(ind.objectives or ()) for ind in pop]
    fronts = fast_non_dominated_sort(objs)
    rank: Dict[int, int] = {}
    crowd: Dict[int, float] = {}
    for fi, front in enumerate(fronts):
        d = crowding_distance(objs, front)
        for idx, c in zip(front, d):
            rank[idx] = fi
            crowd[idx] = c
    return rank, crowd


def _tournament(pop: List[EncodedIndividual], rank: Dict[int, int], crowd: Dict[int, float], rng) -> EncodedIndividual:
    i, j = rng.py_rng.sample(range(len(pop)), 2)
    if rank[i] < rank[j]:
        return pop[i]
    if rank[j] < rank[i]:
        return pop[j]
    if crowd[i] > crowd[j]:
        return pop[i]
    if crowd[j] > crowd[i]:
        return pop[j]
    return pop[i] if rng.py_rng.random() < 0.5 else pop[j]


def _select(pop: List[EncodedIndividual], popsize: int) -> List[EncodedIndividual]:
    objs = [tuple(ind.objectives or ()) for ind in pop]
    fronts = fast_non_dominated_sort(objs)
    selected: List[EncodedIndividual] = []
    for front in fronts:
        if len(selected) + len(front) <= popsize:
            selected.extend(pop[i] for i in front)
            continue
        dist = crowding_distance(objs, front)
        ranked = sorted(zip(front, dist), key=lambda x: x[1], reverse=True)
        selected.extend(pop[i] for i, _ in ranked[: popsize - len(selected)])
        break
    return selected


def _crossover(
    p1: EncodedIndividual,
    p2: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng,
) -> EncodedIndividual:
    child = EncodedIndividual(ua={}, os={}, op={}, ms={})
    for job in instance.jobs:
        child.ua[job.job_id] = p1.ua[job.job_id] if rng.py_rng.random() < 0.5 else p2.ua[job.job_id]
    for t in range(1, instance.num_types + 1):
        v1 = p1.os.get(t, [])
        v2 = p2.os.get(t, [])
        cp = rng.py_rng.randrange(len(v1)) if v1 else 0
        child.os[t] = list(v1[:cp]) + list(v2[cp:])
    child.op = op_from_ua_os(instance, child.ua, child.os)  # type: ignore[arg-type]
    for sru_id, seq in child.op.items():
        mvec: List[int] = []
        for item in seq:
            chosen = None
            for parent in (p1, p2):
                pseq = parent.op.get(sru_id, [])
                pms = parent.ms.get(sru_id, [])
                for idx, parent_item in enumerate(pseq):
                    if item == parent_item and idx < len(pms):
                        chosen = pms[idx]
                        break
                if chosen is not None:
                    break
            mvec.append(int(chosen or 0))
        child.ms[sru_id] = mvec
    return repair_mvc_individual(child, instance, mode, rng)


def _mutate(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng,
    mr: float,
) -> EncodedIndividual:
    out = deepcopy(ind)
    compatible = build_mvc_compatible_sru_map(instance, mode)
    for job in instance.jobs:
        if rng.py_rng.random() < mr:
            choices = compatible[job.job_id]
            out.ua[job.job_id] = int(rng.py_rng.choice(choices))
    for vec in out.os.values():
        if len(vec) > 1 and rng.py_rng.random() < mr:
            i, j = rng.py_rng.sample(range(len(vec)), 2)
            vec[i], vec[j] = vec[j], vec[i]
    out.op = op_from_ua_os(instance, out.ua, out.os)  # type: ignore[arg-type]
    for sru_id, seq in out.op.items():
        if sru_id not in out.ms:
            out.ms[sru_id] = []
        while len(out.ms[sru_id]) < len(seq):
            out.ms[sru_id].append(0)
        for i in range(len(seq)):
            if rng.py_rng.random() < mr:
                out.ms[sru_id][i] = 0
    return repair_mvc_individual(out, instance, mode, rng)


def run_mvc_nsgaii(
    instance: MVCSMDFJSPInstance,
    cfg: MVCNSGAIIConfig,
    mode: MVCModeConfig | None = None,
) -> MVCRunResult:
    mode = mode or MVCModeConfig()
    rng = make_rng(cfg.seed)
    if cfg.max_evaluations is not None and cfg.max_evaluations < cfg.popsize:
        raise ValueError("max_evaluations must be at least popsize")
    tracker = EvaluationTracker(cfg.max_evaluations)
    if cfg.time_measure not in {"wall", "cpu"}:
        raise ValueError("time_measure must be 'wall' or 'cpu'")
    clock = time.process_time if cfg.time_measure == "cpu" else time.perf_counter
    wall_start = time.perf_counter()
    budget_start = clock()
    deadline_s = budget_start + cfg.time_limit_s
    phase_times = {"initialization": 0.0, "variation": 0.0, "evaluation": 0.0, "selection": 0.0}
    phase_start = clock()
    pop = [build_random_mvc_individual(instance, mode, rng) for _ in range(cfg.popsize)]
    evaluate_mvc_population(instance, pop, mode, tracker)
    phase_times["initialization"] += clock() - phase_start
    history: List[Dict[str, float]] = []
    stop_reason = "max_iter"

    for it in range(1, cfg.max_iter + 1):
        if clock() >= deadline_s:
            stop_reason = "time_limit"
            break
        if tracker.exhausted:
            stop_reason = "max_evaluations"
            break
        phase_start = clock()
        rank, crowd = _rank_and_crowding(pop)
        phase_times["selection"] += clock() - phase_start
        offspring: List[EncodedIndividual] = []
        while len(offspring) < cfg.popsize:
            if clock() >= deadline_s:
                stop_reason = "time_limit"
                break
            if tracker.exhausted:
                stop_reason = "max_evaluations"
                break
            phase_start = clock()
            p1 = _tournament(pop, rank, crowd, rng)
            p2 = _tournament(pop, rank, crowd, rng)
            if rng.py_rng.random() < cfg.cr:
                child = _crossover(p1, p2, instance, mode, rng)
            else:
                child = deepcopy(p1)
            child = _mutate(child, instance, mode, rng, cfg.mr)
            phase_times["variation"] += clock() - phase_start
            phase_start = clock()
            evaluate_mvc_population(instance, [child], mode, tracker)
            phase_times["evaluation"] += clock() - phase_start
            offspring.append(child)
            phase_start = clock()
        if not offspring:
            break
        phase_start = clock()
        pop = _select(pop + offspring, cfg.popsize)
        phase_times["selection"] += clock() - phase_start
        objs = [tuple(x.objectives or ()) for x in pop if x.objectives is not None]
        best = [min(o[d] for o in objs) for d in range(2)]
        row = {
            "iter": float(it),
            "best_cost": best[0],
            "best_makespan": best[1],
            "evaluations": float(tracker.evaluations),
            "elapsed_s": float(clock() - budget_start),
            "wall_elapsed_s": float(time.perf_counter() - wall_start),
        }
        history.append(row)
        if clock() >= deadline_s:
            stop_reason = "time_limit"
            break
        if tracker.exhausted:
            stop_reason = "max_evaluations"
            break

    nd = merge_non_dominated(
        [],
        [(tuple(ind.objectives or ()), ind) for ind in pop if ind.objectives is not None],
        max_size=cfg.nd_pool_max,
    )
    if not history and stop_reason not in {"time_limit", "max_evaluations"}:
        stop_reason = "completed_without_iteration"
    elapsed_s = time.perf_counter() - wall_start
    budget_elapsed_s = clock() - budget_start
    return MVCRunResult(
        nd_solutions=[x[1] for x in nd],
        history=history,
        stop_reason=stop_reason,
        iterations_completed=len(history),
        elapsed_s=elapsed_s,
        evaluations_completed=tracker.evaluations,
        phase_times={**phase_times, "total": budget_elapsed_s},
        budget_elapsed_s=budget_elapsed_s,
        time_measure=cfg.time_measure,
    )
