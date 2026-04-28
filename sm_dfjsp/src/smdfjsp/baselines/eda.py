from __future__ import annotations

from smdfjsp.core.types import SMDFJSPInstance
from smdfjsp.eda_ts.algorithm import EDATS, EDATSConfig, RunResult


def run_eda(instance: SMDFJSPInstance, cfg: EDATSConfig) -> RunResult:
    base = EDATSConfig(**cfg.__dict__)
    base.use_ts = False
    base.use_multi_population = False
    base.use_nd_memory = False
    algo = EDATS(instance, base)
    return algo.run()


def run_eda_vns(instance: SMDFJSPInstance, cfg: EDATSConfig) -> RunResult:
    base = EDATSConfig(**cfg.__dict__)
    base.use_ts = True
    base.use_multi_population = False
    base.use_nd_memory = False
    base.tmax = max(3, cfg.tmax // 2)
    algo = EDATS(instance, base)
    return algo.run()

