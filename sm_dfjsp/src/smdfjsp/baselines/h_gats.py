from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Dict, List

from smdfjsp.baselines.common import evaluate_population, nsga2_select
from smdfjsp.baselines.variation import crossover, mutate
from smdfjsp.core.encoding import build_option_index, build_random_individual
from smdfjsp.core.pareto import merge_non_dominated
from smdfjsp.core.random_utils import make_rng
from smdfjsp.core.types import EncodedIndividual, SMDFJSPInstance
from smdfjsp.eda_ts.algorithm import EDATS, EDATSConfig, RunResult


@dataclass
class HGATSConfig:
    popsize: int = 50
    max_iter: int = 100
    time_limit_s: float = 100.0
    cr: float = 0.2
    mr: float = 0.02
    t: int = 40
    epsilon: float = 0.008
    seed: int = 42
    nd_pool_max: int = 300


def run_h_gats(instance: SMDFJSPInstance, cfg: HGATSConfig) -> RunResult:
    rng = make_rng(cfg.seed)
    option_index = build_option_index(instance)
    pop = [build_random_individual(instance, option_index, rng) for _ in range(cfg.popsize)]
    evaluate_population(instance, pop)
    history: List[Dict[str, float]] = []

    ts_helper = EDATS(
        instance,
        EDATSConfig(
            popsize=cfg.popsize,
            max_iter=1,
            time_limit_s=cfg.time_limit_s,
            epsilon=cfg.epsilon,
            tmax=max(1, cfg.t),
            seed=cfg.seed,
            use_multi_population=False,
            use_nd_memory=False,
            use_ts=True,
        ),
    )
    start = time.time()
    for it in range(1, cfg.max_iter + 1):
        if (time.time() - start) >= cfg.time_limit_s:
            break
        offspring: List[EncodedIndividual] = []
        while len(offspring) < cfg.popsize:
            p1 = rng.py_rng.choice(pop)
            p2 = rng.py_rng.choice(pop)
            if rng.py_rng.random() < cfg.cr:
                child = crossover(p1, p2, instance, option_index, rng)
            else:
                child = mutate(p1, instance, option_index, rng, cfg.mr)
            child = mutate(child, instance, option_index, rng, cfg.mr)
            offspring.append(child)
        evaluate_population(instance, offspring)
        merged = nsga2_select(pop + offspring, cfg.popsize)

        # TS local improvement on top candidates.
        merged_sorted = sorted(merged, key=lambda x: x.objectives[0] + x.objectives[1])  # type: ignore[index]
        local_take = max(1, cfg.popsize // 10)
        improved = [ts_helper._tabu_search(ind) for ind in merged_sorted[:local_take]]  # noqa: SLF001
        evaluate_population(instance, improved)
        pop = nsga2_select(merged + improved, cfg.popsize)

        objs = [x.objectives for x in pop if x.objectives is not None]
        history.append({"iter": it, "best_cost": min(o[0] for o in objs), "best_makespan": min(o[1] for o in objs)})

    nd = merge_non_dominated(
        [],
        [(ind.objectives, ind) for ind in pop if ind.objectives is not None],
        max_size=cfg.nd_pool_max,
    )
    return RunResult(nd_solutions=[x[1] for x in nd], history=history)

