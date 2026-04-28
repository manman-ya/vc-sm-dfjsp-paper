from __future__ import annotations

import math
import unittest
from collections import Counter

from smdfjsp.core.encoding import build_compatible_sru_map, build_option_index, op_from_ua_os, repair_individual
from smdfjsp.core.random_utils import make_rng
from smdfjsp.core.types import EncodedIndividual, Job, Operation, ProcessOption, SMDFJSPInstance, SRU
from smdfjsp.model.evaluator import evaluate_individual


def _build_small_instance() -> SMDFJSPInstance:
    srus = [
        SRU(sru_id=1, type_id=1, machine_ids=[1, 2]),
        SRU(sru_id=2, type_id=1, machine_ids=[1, 2]),
    ]
    jobs = []
    for job_id in [1, 2, 3]:
        ops = [
            Operation(
                op_id=1,
                options=[
                    ProcessOption(1, 1, 3, 2),
                    ProcessOption(1, 2, 2, 3),
                    ProcessOption(2, 1, 4, 2),
                    ProcessOption(2, 2, 2, 4),
                ],
            ),
            Operation(
                op_id=2,
                options=[
                    ProcessOption(1, 1, 2, 2),
                    ProcessOption(1, 2, 3, 2),
                    ProcessOption(2, 1, 3, 2),
                    ProcessOption(2, 2, 1, 5),
                ],
            ),
        ]
        jobs.append(Job(job_id=job_id, type_id=1, operations=ops))

    transport_time = {}
    transport_cost = {}
    for j in [1, 2, 3]:
        transport_time[(j, 1)] = 1
        transport_time[(j, 2)] = 2
        transport_cost[(j, 1)] = 3
        transport_cost[(j, 2)] = 2

    return SMDFJSPInstance(
        name="tiny_smdfjsp",
        num_types=1,
        jobs=jobs,
        srus=srus,
        transport_time=transport_time,
        transport_cost_per_time=transport_cost,
    )


def _build_cross_type_instance() -> SMDFJSPInstance:
    srus = [
        SRU(sru_id=1, type_id=1, machine_ids=[1]),
        SRU(sru_id=2, type_id=2, machine_ids=[1]),
    ]
    jobs = [
        Job(
            job_id=1,
            type_id=1,
            operations=[Operation(op_id=1, options=[ProcessOption(1, 1, 2, 3), ProcessOption(2, 1, 2, 3)])],
        )
    ]
    transport_time = {(1, 1): 1, (1, 2): 1}
    transport_cost = {(1, 1): 1, (1, 2): 1}
    return SMDFJSPInstance(
        name="cross_type_case",
        num_types=2,
        jobs=jobs,
        srus=srus,
        transport_time=transport_time,
        transport_cost_per_time=transport_cost,
    )


class TestModelConstraints(unittest.TestCase):
    def test_valid_individual_is_feasible(self) -> None:
        inst = _build_small_instance()
        ua = {1: 1, 2: 2, 3: 1}
        os_layer = {1: [1, 2, 3, 1, 2, 3]}
        op = op_from_ua_os(inst, ua, os_layer)
        option_index = build_option_index(inst)
        ms = {sru_id: [sorted(option_index[(j, o, sru_id)].keys())[0] for (j, o) in seq] for sru_id, seq in op.items()}
        ind = EncodedIndividual(ua=ua, os=os_layer, op=op, ms=ms)

        ev = evaluate_individual(inst, ind)
        self.assertTrue(ev.feasible)
        self.assertTrue(math.isfinite(ev.objectives[0]))
        self.assertTrue(math.isfinite(ev.objectives[1]))
        self.assertEqual(len(ev.records), 6)

    def test_invalid_os_is_rejected(self) -> None:
        inst = _build_small_instance()
        ua = {1: 1, 2: 2, 3: 1}
        # Expected token count is 6, this vector is intentionally invalid.
        os_layer = {1: [1, 2, 1]}
        ind = EncodedIndividual(ua=ua, os=os_layer, op={}, ms={})

        ev = evaluate_individual(inst, ind)
        self.assertFalse(ev.feasible)
        self.assertEqual(ev.message, "invalid OS multiset")
        self.assertTrue(math.isinf(ev.objectives[0]))
        self.assertTrue(math.isinf(ev.objectives[1]))

    def test_type_mismatch_is_rejected(self) -> None:
        inst = _build_cross_type_instance()
        ua = {1: 2}  # type-1 job assigned to type-2 SRU
        os_layer = {1: [1], 2: []}
        op = op_from_ua_os(inst, ua, os_layer)
        ms = {2: [1]}
        ind = EncodedIndividual(ua=ua, os=os_layer, op=op, ms=ms)

        ev = evaluate_individual(inst, ind)
        self.assertFalse(ev.feasible)
        self.assertEqual(ev.message, "type mismatch")
        self.assertTrue(math.isinf(ev.objectives[0]))
        self.assertTrue(math.isinf(ev.objectives[1]))

    def test_missing_transport_is_rejected(self) -> None:
        inst = _build_small_instance()
        del inst.transport_time[(1, 1)]

        ua = {1: 1, 2: 2, 3: 1}
        os_layer = {1: [1, 2, 3, 1, 2, 3]}
        op = op_from_ua_os(inst, ua, os_layer)
        option_index = build_option_index(inst)
        ms = {sru_id: [sorted(option_index[(j, o, sru_id)].keys())[0] for (j, o) in seq] for sru_id, seq in op.items()}
        ind = EncodedIndividual(ua=ua, os=os_layer, op=op, ms=ms)

        ev = evaluate_individual(inst, ind)
        self.assertFalse(ev.feasible)
        self.assertEqual(ev.message, "transport miss")
        self.assertTrue(math.isinf(ev.objectives[0]))
        self.assertTrue(math.isinf(ev.objectives[1]))

    def test_repair_individual_restores_compatibility(self) -> None:
        inst = _build_small_instance()
        option_index = build_option_index(inst)
        compatible = build_compatible_sru_map(inst, option_index)
        rng = make_rng(20260428)

        bad = EncodedIndividual(
            ua={1: 99, 2: 99, 3: 99},
            os={1: [1, 1, 2]},  # invalid multiset
            op={},
            ms={},
        )
        fixed = repair_individual(bad, inst, option_index, rng)

        for job_id, sru_id in fixed.ua.items():
            self.assertIn(sru_id, compatible[job_id])

        self.assertEqual(len(fixed.os[1]), 6)
        self.assertEqual(Counter(fixed.os[1]), Counter([1, 1, 2, 2, 3, 3]))


if __name__ == "__main__":
    unittest.main()

