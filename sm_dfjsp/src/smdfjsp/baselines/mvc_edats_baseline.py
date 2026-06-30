from __future__ import annotations

from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.mvc_eda_ts import MVCEDATS, MVCEDATSConfig
from smdfjsp.mvc_eda_ts.algorithm import MVCEDATSResult


def run_mvc_edats_baseline(
    instance: MVCSMDFJSPInstance,
    cfg: MVCEDATSConfig,
    mode: MVCModeConfig | None = None,
) -> MVCEDATSResult:
    base_cfg = MVCEDATSConfig(
        popsize=cfg.popsize,
        max_iter=cfg.max_iter,
        time_limit_s=cfg.time_limit_s,
        alpha=cfg.alpha,
        beta=cfg.beta,
        gamma=cfg.gamma,
        mu=cfg.mu,
        epsilon=cfg.epsilon,
        tmax=cfg.tmax,
        elite_ratio=cfg.elite_ratio,
        local_search_steps=max(0, cfg.local_search_steps // 2),
        nd_pool_max=cfg.nd_pool_max,
        max_evaluations=cfg.max_evaluations,
        time_measure=cfg.time_measure,
        seed=cfg.seed,
        use_value_chain_init=False,
        use_value_chain_prior=False,
        use_probability_model=True,
        use_cross_chain_neighbors=False,
        use_bottleneck_release=False,
        use_critical_migration=False,
        use_cost_return=False,
        use_adaptive_neighborhood=False,
        use_nd_memory=cfg.use_nd_memory,
    )
    return MVCEDATS(instance, base_cfg, mode).run()
