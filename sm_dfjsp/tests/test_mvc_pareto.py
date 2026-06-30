from __future__ import annotations

import unittest
import sys
from pathlib import Path

from smdfjsp.metrics.multiobjective import (
    crowding_distance,
    dominates,
    get_non_dominated_indices,
    hypervolume,
    igd,
    normalized_igd,
    normalized_hypervolume,
    raw_igd,
)

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mvc_experiment_utils import summarize_metrics


class TestMVCPareto(unittest.TestCase):
    def test_two_dimensional_dominance(self) -> None:
        self.assertTrue(dominates((1, 2), (1, 3)))
        self.assertFalse(dominates((1, 4), (2, 3)))

    def test_non_dominated_indices_and_crowding(self) -> None:
        pts = [(1, 5), (2, 3), (3, 2), (2, 4)]
        nd = get_non_dominated_indices(pts)
        self.assertEqual(set(nd), {0, 1, 2})
        distances = crowding_distance(pts, nd)
        self.assertEqual(len(distances), len(nd))

    def test_normalized_hypervolume_is_dimensionless(self) -> None:
        front = [(2, 8), (5, 5), (8, 2)]
        ref = (10, 10)
        raw_hv = hypervolume(front, ref)
        norm_hv = normalized_hypervolume(front, ref, (0, 0), (10, 10))

        self.assertAlmostEqual(raw_hv, 37.0)
        self.assertAlmostEqual(norm_hv, 0.37)

    def test_normalized_igd_is_scale_invariant(self) -> None:
        front = [(2, 10), (10, 2)]
        reference = [(0, 10), (10, 0)]
        scaled_front = [(20_000, 1_000), (100_000, 200)]
        scaled_reference = [(0, 1_000), (100_000, 0)]

        value = normalized_igd(front, reference, (0, 0), (10, 10))
        scaled_value = normalized_igd(scaled_front, scaled_reference, (0, 0), (100_000, 1_000))

        self.assertAlmostEqual(value, 0.2)
        self.assertAlmostEqual(scaled_value, value)
        self.assertAlmostEqual(igd(front, reference), value)
        self.assertEqual(raw_igd(front, reference), 2.0)
        self.assertGreater(raw_igd(scaled_front, scaled_reference), raw_igd(front, reference))

    def test_summarize_metrics_reports_normalized_hv_and_raw_hv(self) -> None:
        rows = [
            {"instance": "i1", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 2, "makespan": 8},
            {"instance": "i1", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 5, "makespan": 5},
            {"instance": "i1", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 8, "makespan": 2},
            {"instance": "i1", "algorithm": "b", "cross_chain": "off", "seed": "1", "total_cost": 9, "makespan": 9},
        ]

        [a_row, b_row] = summarize_metrics(rows, objective_dim=2)

        self.assertEqual(a_row["algorithm"], "a")
        self.assertIn("raw_hv", a_row)
        self.assertIn("raw_igd", a_row)
        self.assertGreater(a_row["raw_hv"], 1.0)
        self.assertGreater(a_row["hv"], 0.0)
        self.assertLessEqual(a_row["hv"], 1.0)
        self.assertLess(b_row["hv"], a_row["hv"])

    def test_summarize_metrics_normalizes_igd_per_instance(self) -> None:
        rows = [
            {"instance": "i1", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 0, "makespan": 10},
            {"instance": "i1", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 10, "makespan": 0},
            {"instance": "i1", "algorithm": "b", "cross_chain": "off", "seed": "1", "total_cost": 2, "makespan": 10},
            {"instance": "i1", "algorithm": "b", "cross_chain": "off", "seed": "1", "total_cost": 10, "makespan": 2},
            {"instance": "i2", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 0, "makespan": 1_000},
            {"instance": "i2", "algorithm": "a", "cross_chain": "off", "seed": "1", "total_cost": 100_000, "makespan": 0},
            {"instance": "i2", "algorithm": "b", "cross_chain": "off", "seed": "1", "total_cost": 20_000, "makespan": 1_000},
            {"instance": "i2", "algorithm": "b", "cross_chain": "off", "seed": "1", "total_cost": 100_000, "makespan": 200},
        ]

        metrics = summarize_metrics(rows, objective_dim=2)
        by_key = {(row["instance"], row["algorithm"]): row for row in metrics}

        self.assertAlmostEqual(by_key[("i1", "b")]["igd"], 0.2)
        self.assertAlmostEqual(by_key[("i2", "b")]["igd"], 0.2)
        self.assertEqual(by_key[("i1", "b")]["raw_igd"], 2.0)
        self.assertGreater(by_key[("i2", "b")]["raw_igd"], by_key[("i1", "b")]["raw_igd"])


if __name__ == "__main__":
    unittest.main()
