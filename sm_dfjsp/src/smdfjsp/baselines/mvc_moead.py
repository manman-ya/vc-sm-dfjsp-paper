from __future__ import annotations

import math
import time
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Sequence, Tuple

from smdfjsp.baselines.mvc_nsgaii import MVCRunResult, _crossover, _mutate
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import make_rng
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.metrics.multiobjective import merge_non_dominated
from smdfjsp.model.mvc_evaluator import EvaluationTracker, evaluate_mvc_individual, evaluate_mvc_population
from smdfjsp.model.mvc_repair import build_random_mvc_individual


@dataclass
class MVCMOEADConfig:
    popsize: int = 50
    max_iter: int = 100
    time_limit_s: float = 100.0
    cr: float = 0.7
    mr: float = 0.3
    neighbor_size: int = 10
    replacements: int = 2
    seed: int = 42
    nd_pool_max: int = 300
    max_evaluations: int | None = None
    time_measure: str = "wall"


def _weight_vectors(popsize: int, dim: int) -> List[Tuple[float, ...]]:
    if dim == 2:
        if popsize <= 1:
            return [(0.5, 0.5)]
        return [(i / (popsize - 1), 1.0 - i / (popsize - 1)) for i in range(popsize)]
    raise ValueError("MOEA/D supports the two formal MVC objectives")


def _neighborhood(weights: Sequence[Sequence[float]], size: int) -> List[List[int]]:
    out: List[List[int]] = []
    n = len(weights)
    k = max(1, min(size, n))
    for i, wi in enumerate(weights):
        ordered = sorted(
            range(n),
            key=lambda j: math.sqrt(sum((float(wi[d]) - float(weights[j][d])) ** 2 for d in range(len(wi)))),
        )
        out.append(ordered[:k])
    return out


def _scalarize(obj: Sequence[float], weight: Sequence[float], ideal: Sequence[float]) -> float:
    # Tchebycheff aggregation for minimization. A tiny epsilon keeps zero weights active.
    return max(max(float(w), 1e-6) * abs(float(o) - float(z)) for o, w, z in zip(obj, weight, ideal))


def _best_values(pop: Sequence[EncodedIndividual], dim: int) -> List[float]:
    objs = [tuple(ind.objectives or ()) for ind in pop if ind.objectives is not None]
    return [min(float(o[d]) for o in objs) for d in range(dim)]


def run_mvc_moead(
    instance: MVCSMDFJSPInstance,
    cfg: MVCMOEADConfig,
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
    phase_times = {
        "initialization": 0.0,
        "variation": 0.0,
        "evaluation": 0.0,
        "replacement": 0.0,
        "archive": 0.0,
    }
    phase_start = clock()
    pop = [build_random_mvc_individual(instance, mode, rng) for _ in range(cfg.popsize)]
    evaluate_mvc_population(instance, pop, mode, tracker)
    weights = _weight_vectors(cfg.popsize, mode.objective_dim)
    neighbors = _neighborhood(weights, cfg.neighbor_size)
    ideal = _best_values(pop, mode.objective_dim)
    archive = merge_non_dominated(
        [],
        [(tuple(ind.objectives or ()), ind) for ind in pop if ind.objectives is not None],
        max_size=cfg.nd_pool_max,
    )
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
        order = list(range(cfg.popsize))
        rng.py_rng.shuffle(order)
        for i in order:
            if clock() >= deadline_s:
                stop_reason = "time_limit"
                break
            if tracker.exhausted:
                stop_reason = "max_evaluations"
                break
            mating_pool = neighbors[i] if len(neighbors[i]) >= 2 else list(range(cfg.popsize))
            phase_start = clock()
            p1_idx, p2_idx = rng.py_rng.sample(mating_pool, 2)
            if rng.py_rng.random() < cfg.cr:
                child = _crossover(pop[p1_idx], pop[p2_idx], instance, mode, rng)
            else:
                child = deepcopy(pop[p1_idx])
            child = _mutate(child, instance, mode, rng, cfg.mr)
            phase_times["variation"] += clock() - phase_start
            phase_start = clock()
            ev = evaluate_mvc_individual(instance, child, mode, tracker)
            phase_times["evaluation"] += clock() - phase_start
            if not ev.feasible:
                continue
            child.objectives = ev.objectives  # type: ignore[assignment]
            child.feasible = ev.feasible
            ideal = [min(ideal[d], float(ev.objectives[d])) for d in range(mode.objective_dim)]

            phase_start = clock()
            replaced = 0
            update_scope = list(neighbors[i])
            rng.py_rng.shuffle(update_scope)
            for j in update_scope:
                current = pop[j]
                if current.objectives is None:
                    continue
                if _scalarize(ev.objectives, weights[j], ideal) <= _scalarize(current.objectives, weights[j], ideal):
                    pop[j] = deepcopy(child)
                    replaced += 1
                    if replaced >= max(1, cfg.replacements):
                        break
            phase_times["replacement"] += clock() - phase_start
            phase_start = clock()
            archive = merge_non_dominated(archive, [(tuple(ev.objectives), child)], max_size=cfg.nd_pool_max)
            phase_times["archive"] += clock() - phase_start

        best = _best_values(pop, mode.objective_dim)
        row = {
            "iter": float(it),
            "best_cost": best[0],
            "best_makespan": best[1],
            "nd_size": float(len(archive)),
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

    archive = merge_non_dominated(
        archive,
        [(tuple(ind.objectives or ()), ind) for ind in pop if ind.objectives is not None],
        max_size=cfg.nd_pool_max,
    )
    if not history and stop_reason not in {"time_limit", "max_evaluations"}:
        stop_reason = "completed_without_iteration"
    elapsed_s = time.perf_counter() - wall_start
    budget_elapsed_s = clock() - budget_start
    return MVCRunResult(
        nd_solutions=[x[1] for x in archive],
        history=history,
        stop_reason=stop_reason,
        iterations_completed=len(history),
        elapsed_s=elapsed_s,
        evaluations_completed=tracker.evaluations,
        phase_times={**phase_times, "total": budget_elapsed_s},
        budget_elapsed_s=budget_elapsed_s,
        time_measure=cfg.time_measure,
    )
