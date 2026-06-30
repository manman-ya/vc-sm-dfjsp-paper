from __future__ import annotations

from pathlib import Path
import math
import unittest

from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.core.random_utils import make_rng
from smdfjsp.data.mvc_io import get_cross_chain_srus, get_intra_chain_srus, load_mvc_instance_json
from smdfjsp.model.mvc_evaluator import evaluate_mvc_individual
from smdfjsp.model.mvc_repair import build_random_mvc_individual, repair_mvc_individual


ROOT = Path(__file__).resolve().parents[1]
MVC_MK05 = ROOT / "data" / "mvc_mk01_15_2vc4sru_equalproc_vcpenalty" / "mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json"


class TestMVCEvaluator(unittest.TestCase):
    def test_cross_off_random_solution_has_no_cross_jobs(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        mode = MVCModeConfig(cross_chain_allowed=False, objective_dim=2)
        ind = build_random_mvc_individual(inst, mode, make_rng(20260428))
        ev = evaluate_mvc_individual(inst, ind, mode)
        self.assertTrue(ev.feasible, ev.message)
        self.assertEqual(ev.diagnostics["cross_chain_jobs"], 0)
        self.assertEqual(ev.cost_breakdown["cross_fixed_cost"], 0.0)
        self.assertEqual(ev.cost_breakdown["cross_variable_cost"], 0.0)
        self.assertEqual(len(ev.objectives), 2)
        self.assertTrue(all(math.isfinite(x) for x in ev.objectives))

    def test_cross_on_cross_assignment_counts_costs(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
        rng = make_rng(20260429)
        ind = build_random_mvc_individual(inst, mode, rng)
        first_job = inst.jobs[0]
        cross = get_cross_chain_srus(first_job, inst)
        self.assertGreater(len(cross), 0)
        ind.ua[first_job.job_id] = cross[0]
        ind = repair_mvc_individual(ind, inst, mode, rng)
        ev = evaluate_mvc_individual(inst, ind, mode)
        self.assertTrue(ev.feasible, ev.message)
        self.assertGreaterEqual(ev.diagnostics["cross_chain_jobs"], 1)
        self.assertGreater(ev.cost_breakdown["cross_fixed_cost"], 0.0)

    def test_total_cost_uses_fixed_cross_cost_only(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        mode = MVCModeConfig(cross_chain_allowed=True, objective_dim=2)
        rng = make_rng(20260528)
        ind = build_random_mvc_individual(inst, mode, rng)
        first_job = inst.jobs[0]
        cross = get_cross_chain_srus(first_job, inst)
        self.assertGreater(len(cross), 0)
        ind.ua[first_job.job_id] = cross[0]
        ind = repair_mvc_individual(ind, inst, mode, rng)
        ev = evaluate_mvc_individual(inst, ind, mode)
        self.assertTrue(ev.feasible, ev.message)
        expected = (
            ev.cost_breakdown["processing_cost"]
            + ev.cost_breakdown["transport_cost"]
            + ev.cost_breakdown["cross_fixed_cost"]
        )
        self.assertAlmostEqual(ev.total_cost, expected)
        self.assertEqual(ev.cost_breakdown["cross_variable_cost"], 0.0)

    def test_cross_off_repair_removes_cross_assignment(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        mode_on = MVCModeConfig(cross_chain_allowed=True)
        mode_off = MVCModeConfig(cross_chain_allowed=False)
        rng = make_rng(20260430)
        ind = build_random_mvc_individual(inst, mode_on, rng)
        job = inst.jobs[0]
        ind.ua[job.job_id] = get_cross_chain_srus(job, inst)[0]
        fixed = repair_mvc_individual(ind, inst, mode_off, rng)
        self.assertIn(fixed.ua[job.job_id], get_intra_chain_srus(job, inst))
        ev = evaluate_mvc_individual(inst, fixed, mode_off)
        self.assertTrue(ev.feasible, ev.message)
        self.assertEqual(ev.diagnostics["cross_chain_jobs"], 0)


if __name__ == "__main__":
    unittest.main()
