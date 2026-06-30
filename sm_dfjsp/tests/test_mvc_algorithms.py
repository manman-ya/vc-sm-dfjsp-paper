from __future__ import annotations

from pathlib import Path
import math
import unittest

from smdfjsp.baselines.mvc_moead import MVCMOEADConfig, run_mvc_moead
from smdfjsp.baselines.mvc_nsgaii import MVCNSGAIIConfig, run_mvc_nsgaii
from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.data.mvc_io import load_mvc_instance_json
from smdfjsp.mvc_eda_ts import MVCEDATS, MVCEDATSConfig


ROOT = Path(__file__).resolve().parents[1]
MVC_MK05 = ROOT / "data" / "mvc_mk01_15_2vc4sru_equalproc_vcpenalty" / "mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json"


def _finite_count(result) -> int:
    count = 0
    for sol in result.nd_solutions:
        if sol.objectives is None:
            continue
        self_finite = all(math.isfinite(float(x)) for x in sol.objectives)
        count += int(self_finite)
    return count


class TestMVCAlgorithms(unittest.TestCase):
    def test_mvc_nsgaii_smoke_cross_off_and_on(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        cfg = MVCNSGAIIConfig(popsize=8, max_iter=2, time_limit_s=10.0, seed=20260428)
        for cross in (False, True):
            mode = MVCModeConfig(cross_chain_allowed=cross, objective_dim=2)
            result = run_mvc_nsgaii(inst, cfg, mode)
            self.assertGreater(len(result.nd_solutions), 0)
            self.assertGreater(_finite_count(result), 0)
            self.assertEqual(result.stop_reason, "max_iter")
            self.assertEqual(result.iterations_completed, 2)

    def test_mvc_moead_smoke_cross_on(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        cfg = MVCMOEADConfig(popsize=8, max_iter=2, time_limit_s=10.0, seed=20260428)
        mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
        result = run_mvc_moead(inst, cfg, mode)
        self.assertGreater(len(result.nd_solutions), 0)
        self.assertGreater(_finite_count(result), 0)
        self.assertEqual(result.stop_reason, "max_iter")
        self.assertEqual(result.iterations_completed, 2)

    def test_mvc_edats_smoke_two_objective(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        cfg = MVCEDATSConfig(popsize=8, max_iter=2, time_limit_s=10.0, local_search_steps=1, seed=20260428)
        mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
        result = MVCEDATS(inst, cfg, mode).run()
        self.assertGreater(len(result.nd_solutions), 0)
        self.assertGreater(_finite_count(result), 0)
        self.assertEqual(result.stop_reason, "max_iter")
        self.assertEqual(result.iterations_completed, 2)
        for sol in result.nd_solutions:
            if sol.objectives is not None:
                self.assertEqual(len(sol.objectives), 2)
                break

    def test_mvc_stop_reason_time_limit(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
        cfg = MVCEDATSConfig(popsize=4, max_iter=5, time_limit_s=0.0, local_search_steps=0, seed=20260428)
        result = MVCEDATS(inst, cfg, mode).run()
        self.assertEqual(result.stop_reason, "time_limit")
        self.assertEqual(result.iterations_completed, 0)

    def test_all_algorithms_respect_exact_evaluation_budget(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
        budget = 11
        results = [
            run_mvc_nsgaii(
                inst,
                MVCNSGAIIConfig(popsize=8, max_iter=100, time_limit_s=10.0, max_evaluations=budget),
                mode,
            ),
            run_mvc_moead(
                inst,
                MVCMOEADConfig(popsize=8, max_iter=100, time_limit_s=10.0, max_evaluations=budget),
                mode,
            ),
            MVCEDATS(
                inst,
                MVCEDATSConfig(
                    popsize=8,
                    max_iter=100,
                    time_limit_s=10.0,
                    local_search_steps=1,
                    max_evaluations=budget,
                ),
                mode,
            ).run(),
        ]
        for result in results:
            self.assertEqual(result.evaluations_completed, budget)
            self.assertEqual(result.stop_reason, "max_evaluations")
            self.assertIsNotNone(result.phase_times)
            self.assertIn("total", result.phase_times or {})


if __name__ == "__main__":
    unittest.main()
