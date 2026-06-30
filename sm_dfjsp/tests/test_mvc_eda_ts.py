from __future__ import annotations

from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.mvc_eda_ts import MVCEDATS, MVCEDATSConfig


def test_mvc_edats_cross_off_smoke(mvc_instance):
    mode = MVCModeConfig(cross_chain_allowed=False, objective_dim=2)
    cfg = MVCEDATSConfig(popsize=6, max_iter=1, time_limit_s=5, seed=12)
    result = MVCEDATS(mvc_instance, cfg, mode).run()
    assert result.nd_solutions
    assert all(sol.feasible for sol in result.nd_solutions)
