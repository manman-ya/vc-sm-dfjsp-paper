from __future__ import annotations

from pathlib import Path
from copy import deepcopy
import unittest

from smdfjsp.core.mvc_types import MVCModeConfig
from smdfjsp.data.mvc_io import (
    get_candidate_srus,
    get_cross_chain_srus,
    get_intra_chain_srus,
    load_mvc_instance_json,
    save_mvc_instance_json,
    validate_mvc_instance,
)


ROOT = Path(__file__).resolve().parents[1]
MVC_MK05 = ROOT / "data" / "mvc_mk01_15_2vc4sru_equalproc_vcpenalty" / "mk05_mvc_2vc_2type_4sru_equalproc_vcpenalty.json"


class TestMVCIO(unittest.TestCase):
    def test_load_mvc_json_and_candidates(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        self.assertEqual(inst.num_jobs, 15)
        self.assertEqual(inst.num_srus, 4)
        self.assertEqual(inst.num_types, 2)

        job = inst.jobs[0]
        intra = get_intra_chain_srus(job, inst)
        cross = get_cross_chain_srus(job, inst)
        self.assertGreaterEqual(len(intra), 1)
        self.assertGreaterEqual(len(cross), 1)

        off = get_candidate_srus(job, inst, MVCModeConfig(cross_chain_allowed=False))
        on = get_candidate_srus(job, inst, MVCModeConfig(cross_chain_allowed=True))
        self.assertEqual(off, intra)
        self.assertEqual(sorted(on), sorted(intra + cross))
        for sid in on:
            sru = inst.sru_map()[sid]
            self.assertIn(job.type_id, sru.service_type_ids)

    def test_round_trip_save_and_negative_validation(self) -> None:
        inst = load_mvc_instance_json(MVC_MK05)
        out = ROOT / "reports" / "_tmp_test_trace" / "mvc_roundtrip.json"
        save_mvc_instance_json(inst, out)
        loaded = load_mvc_instance_json(out)
        self.assertEqual(loaded.num_jobs, inst.num_jobs)
        self.assertEqual(loaded.num_srus, inst.num_srus)
        self.assertEqual(loaded.num_types, inst.num_types)
        self.assertEqual(loaded.jobs[0].value_chain_id, inst.jobs[0].value_chain_id)

        bad = deepcopy(inst)
        target_job = bad.jobs[0]
        for sru in bad.srus:
            if target_job.type_id in sru.service_type_ids:
                sru.value_chain_id = "VC_missing"
        with self.assertRaisesRegex(ValueError, "no intra-chain same-type SRU"):
            validate_mvc_instance(bad)


if __name__ == "__main__":
    unittest.main()
