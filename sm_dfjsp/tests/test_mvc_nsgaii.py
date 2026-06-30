from __future__ import annotations

from smdfjsp.baselines.mvc_nsgaii import MVCNSGAIIConfig, run_mvc_nsgaii
from smdfjsp.core.mvc_types import MVCModeConfig


def test_mvc_nsgaii_cross_on_smoke(mvc_instance):
    mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
    result = run_mvc_nsgaii(mvc_instance, MVCNSGAIIConfig(popsize=6, max_iter=1, time_limit_s=5, seed=11), mode)
    assert result.nd_solutions
    assert all(sol.feasible for sol in result.nd_solutions)
    assert all(len(sol.objectives or ()) == 2 for sol in result.nd_solutions)
