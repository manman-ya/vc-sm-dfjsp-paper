from __future__ import annotations

import json
import math
from pathlib import Path
import unittest

from smdfjsp.baselines import HGATSConfig, NSGAIIConfig, run_eda, run_eda_vns, run_h_gats, run_nsgaii
from smdfjsp.core.types import EncodedIndividual, Job, Operation, ProcessOption, SMDFJSPInstance, SRU
from smdfjsp.eda_ts import EDATS, EDATSConfig


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


def _front_signature(run_result) -> list[tuple[float, float]]:
    pairs = []
    for s in run_result.nd_solutions:
        if s.objectives is None:
            continue
        pairs.append((round(float(s.objectives[0]), 6), round(float(s.objectives[1]), 6)))
    return sorted(set(pairs))


class TestAlgorithmRegression(unittest.TestCase):
    def test_edats_seed_deterministic(self) -> None:
        inst = _build_small_instance()
        cfg = EDATSConfig(
            popsize=12,
            max_iter=4,
            time_limit_s=30.0,
            alpha=0.5,
            beta=0.5,
            gamma=0.5,
            mu=0.1,
            epsilon=0.008,
            tmax=2,
            seed=20260428,
        )

        r1 = EDATS(inst, cfg).run()
        r2 = EDATS(inst, cfg).run()
        sig1 = _front_signature(r1)
        sig2 = _front_signature(r2)
        self.assertGreater(len(sig1), 0)
        self.assertEqual(sig1, sig2)

    def test_edats_ablation_switches_produce_feasible_front(self) -> None:
        inst = _build_small_instance()
        base = EDATSConfig(
            popsize=10,
            max_iter=3,
            time_limit_s=10.0,
            alpha=0.5,
            beta=0.5,
            gamma=0.5,
            mu=0.1,
            epsilon=0.008,
            tmax=2,
            seed=20260428,
        )
        variants = [
            base,
            EDATSConfig(**{**base.__dict__, "use_multi_population": False}),
            EDATSConfig(**{**base.__dict__, "use_nd_memory": False}),
            EDATSConfig(**{**base.__dict__, "use_ts": False}),
        ]

        for cfg in variants:
            result = EDATS(inst, cfg).run()
            self.assertGreater(len(result.nd_solutions), 0)
            self.assertLessEqual(len(result.history), cfg.max_iter)
            finite_count = 0
            for s in result.nd_solutions:
                if s.objectives is None:
                    continue
                self.assertTrue(math.isfinite(float(s.objectives[0])))
                self.assertTrue(math.isfinite(float(s.objectives[1])))
                finite_count += 1
            self.assertGreater(finite_count, 0)

    def test_baselines_run_and_return_front(self) -> None:
        inst = _build_small_instance()

        eda_cfg = EDATSConfig(popsize=10, max_iter=3, time_limit_s=10.0, tmax=2, seed=20260429)
        nsga_cfg = NSGAIIConfig(popsize=10, max_iter=3, time_limit_s=10.0, cr=0.7, mr=0.3, seed=20260429)
        h_cfg = HGATSConfig(popsize=10, max_iter=3, time_limit_s=10.0, cr=0.2, mr=0.02, t=3, seed=20260429)

        results = [
            run_eda(inst, eda_cfg),
            run_eda_vns(inst, eda_cfg),
            run_nsgaii(inst, nsga_cfg),
            run_h_gats(inst, h_cfg),
        ]
        for r in results:
            self.assertGreater(len(r.nd_solutions), 0)
            self.assertGreater(len(_front_signature(r)), 0)

    def test_trace_snapshot_output(self) -> None:
        inst = _build_small_instance()
        td = Path("reports/repro/test_trace_tmp")
        td.mkdir(parents=True, exist_ok=True)
        cfg = EDATSConfig(
            popsize=10,
            max_iter=3,
            time_limit_s=10.0,
            alpha=0.5,
            beta=0.5,
            gamma=0.5,
            mu=0.1,
            epsilon=0.008,
            tmax=2,
            seed=20260430,
            trace_enabled=True,
            trace_dir=str(td),
            trace_every=1,
        )
        result = EDATS(inst, cfg).run()
        self.assertIsNotNone(result.trace_file)
        trace_path = Path(result.trace_file or "")
        self.assertTrue(trace_path.exists())
        lines = [x for x in trace_path.read_text(encoding="utf-8").splitlines() if x.strip()]
        self.assertGreater(len(lines), 0)
        record = json.loads(lines[0])
        self.assertIn("pma", record)
        self.assertIn("pms", record)
        self.assertIn("pmm", record)
        self.assertIn("iter", record)

    def test_move_level_tabu_key_builder(self) -> None:
        dummy = EncodedIndividual(ua={}, os={}, op={}, ms={}, aux={"move_kind": "N1", "job_id": 7, "to_sru": 3})
        key = EDATS._build_tabu_key(dummy)
        self.assertEqual(key, ("N1", 7, 3))

        dummy2 = EncodedIndividual(
            ua={},
            os={},
            op={},
            ms={},
            aux={"move_kind": "N3", "sru_id": 2, "job_id": 5, "op_id": 1, "to_machine": 4},
        )
        key2 = EDATS._build_tabu_key(dummy2)
        self.assertEqual(key2, ("N3", 2, 5, 1, 4))


if __name__ == "__main__":
    unittest.main()
