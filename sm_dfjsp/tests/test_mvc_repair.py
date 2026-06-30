from __future__ import annotations

from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.core.random_utils import make_rng
from smdfjsp.model.mvc_evaluator import evaluate_mvc_individual
from smdfjsp.model.mvc_repair import build_random_mvc_individual, repair_mvc_individual


def test_repair_keeps_cross_off_intra_chain(mvc_instance):
    mode = MVCModeConfig(cross_chain_allowed=False, objective_dim=2)
    ind = build_random_mvc_individual(mvc_instance, MVCModeConfig(cross_chain_allowed=True), make_rng(7))
    repaired = repair_mvc_individual(ind, mvc_instance, mode, make_rng(8))
    ev = evaluate_mvc_individual(mvc_instance, repaired, mode)
    assert ev.feasible
    assert ev.diagnostics["cross_chain_jobs"] == 0
