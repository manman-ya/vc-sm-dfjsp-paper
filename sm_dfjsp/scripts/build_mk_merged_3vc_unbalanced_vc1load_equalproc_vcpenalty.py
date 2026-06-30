from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from build_mk_merged_3vc_equalproc_vcpenalty import (
    SEED,
    SRU_SPECS,
    SYMMETRIC_PAIR_PENALTIES,
    _assert_sanity,
    _cross_penalty,
    _resolve,
    build_payload,
)
from smdfjsp.data.mvc_io import load_mvc_instance_json, validate_mvc_instance


UNBALANCED_JOBS_BY_VC_TYPE: Dict[str, Dict[str, List[int]]] = {
    "VC1": {
        "T1": [1, 3, 5, 6, 12, 14, 16, 17, 18, 20, 21, 22, 23, 25, 26, 28, 32, 34],
        "T2": [2, 4, 8, 9, 10, 11, 13, 15, 19, 24, 27, 29, 30, 37, 45, 48, 58, 59],
    },
    "VC2": {
        "T1": [31, 35, 36, 44, 46, 54],
        "T2": [33, 39, 41, 43, 47, 57],
    },
    "VC3": {
        "T1": [7, 38, 40, 42, 49, 50],
        "T2": [51, 52, 53, 55, 56, 60],
    },
}


def _job_to_vc() -> Dict[int, str]:
    mapping: Dict[int, str] = {}
    for vc, by_type in UNBALANCED_JOBS_BY_VC_TYPE.items():
        for jobs in by_type.values():
            for job_id in jobs:
                if job_id in mapping:
                    raise ValueError(f"duplicate job in unbalanced assignment: J{job_id}")
                mapping[job_id] = vc
    return mapping


def _rebuild_assignment(payload: dict) -> dict:
    job_to_vc = _job_to_vc()
    expected_jobs = {int(job["job_id"]) for job in payload["jobs"]}
    if set(job_to_vc) != expected_jobs:
        missing = sorted(expected_jobs - set(job_to_vc))
        extra = sorted(set(job_to_vc) - expected_jobs)
        raise ValueError(f"unbalanced assignment mismatch; missing={missing}, extra={extra}")

    sru_to_vc = {sid: vc for sid, vc, _ in SRU_SPECS}
    candidate_srus_by_type = {
        "T1": ["U1", "U3", "U5"],
        "T2": ["U2", "U4", "U6"],
    }

    value_chains = {vc: [] for vc in ["VC1", "VC2", "VC3"]}
    types = {typ: [] for typ in ["T1", "T2"]}
    compatibility: Dict[str, dict] = {}
    transport_time: Dict[str, Dict[str, int]] = {}
    transport_cost: Dict[str, Dict[str, float]] = {}
    cross_chain: Dict[str, Dict[str, dict]] = {}

    for job in payload["jobs"]:
        jid = int(job["job_id"])
        typ = str(job["type"])
        vc = job_to_vc[jid]
        all_type_srus = candidate_srus_by_type[typ]
        intra = [sid for sid in all_type_srus if sru_to_vc[sid] == vc]
        cross = [sid for sid in all_type_srus if sru_to_vc[sid] != vc]
        candidates = intra + cross

        job["value_chain"] = vc
        job["candidate_srus"] = candidates
        value_chains[vc].append(jid)
        types[typ].append(jid)
        compatibility[f"J{jid}"] = {
            "candidate_srus": candidates,
            "intra_chain_srus": intra,
            "cross_chain_srus": cross,
        }

        for op in job["operations"]:
            by_sru = op["processing_options_by_sru"]
            op["processing_options_by_sru"] = {sid: by_sru[sid] for sid in candidates}

        jkey = f"J{jid}"
        transport_time[jkey] = {}
        transport_cost[jkey] = {}
        cross_chain[jkey] = {}
        for sid in candidates:
            sru_vc = sru_to_vc[sid]
            is_cross = vc != sru_vc
            if is_cross:
                penalty = _cross_penalty(vc, sru_vc)
                t = int(penalty["transport_time_base"] + jid % 3)
                fixed = float(penalty["cross_chain_fixed_cost"])
                unit_transport_cost = float(penalty["transport_unit_cost"])
            else:
                t = int(2 + jid % 2)
                fixed = 0.0
                unit_transport_cost = 1.8
            transport_time[jkey][sid] = t
            transport_cost[jkey][sid] = float(round(t * unit_transport_cost, 6))
            cross_chain[jkey][sid] = {
                "job_value_chain": vc,
                "sru_value_chain": sru_vc,
                "is_cross_chain": bool(is_cross),
                "cross_chain_fixed_cost": float(round(fixed, 6)),
                "cross_chain_cost_rate": 0.0,
                "estimated_cross_chain_cost": float(round(fixed, 6)),
            }

    payload["instance_name"] = f"{payload['source_instance']}_mvc_3vc_2type_6sru_unbalanced_vc1load_equalproc_vcpenalty"
    payload["seed"] = SEED
    payload["value_chains"] = [
        {"id": label, "name": f"Value chain {label.replace('VC', '')}", "jobs": sorted(jobs)}
        for label, jobs in value_chains.items()
    ]
    payload["types"] = [
        {"id": label, "name": f"Service type {label.replace('T', '')}", "jobs": sorted(jobs)}
        for label, jobs in types.items()
    ]
    payload["job_sru_compatibility"] = compatibility
    payload["transport_time"] = transport_time
    payload["transport_cost"] = transport_cost
    payload["cross_chain"] = cross_chain
    payload["notes"]["value_chain_assignment_rule"] = (
        "Unbalanced VC1-load scenario: VC1 has 36 heavier jobs, VC2 and VC3 have 12 lighter jobs each."
    )
    payload["notes"]["unbalanced_jobs_by_vc_type"] = UNBALANCED_JOBS_BY_VC_TYPE
    payload["notes"]["scenario_purpose"] = (
        "Designed to make VC1-T1 and VC1-T2 SRUs congested under cross-chain-off mode, "
        "so cross-chain-on mode can demonstrate load relief by moving VC1 jobs to same-type SRUs in VC2/VC3."
    )
    return payload


def _write_readme(output_dir: Path) -> None:
    text = """# MVC MK14-MK15 Merged Unbalanced VC1-Load Dataset

Generated from `data/mk/mk14_mk15_merged.txt`.

This scenario keeps the original 60 jobs, 15 base machines, 2 service types, and 6 SRUs, but changes value-chain ownership to create a deliberately congested VC1:

- VC1: 36 jobs, split as 18 T1 and 18 T2.
- VC2: 12 jobs, split as 6 T1 and 6 T2.
- VC3: 12 jobs, split as 6 T1 and 6 T2.
- The global type totals remain balanced: 30 T1 and 30 T2.
- Heavy jobs are assigned preferentially to VC1, making U1=VC1-T1 and U2=VC1-T2 congested in cross-chain-off mode.
- Processing times and processing costs remain equal-processing: each candidate SRU copies the original MK base processing times and machine costs.
- Cross-chain fixed costs remain: VC1-VC2=200.0, VC2-VC3=230.0, VC1-VC3=320.0; variable rate is 0.0.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an unbalanced VC1-load 3VC/2type/6SRU merged MK instance.")
    parser.add_argument("--input", default="data/mk/mk14_mk15_merged.txt")
    parser.add_argument("--output-dir", default="data/mvc_mk_merged_3vc6sru_unbalanced_vc1load_equalproc_vcpenalty")
    args = parser.parse_args()

    mk_path = _resolve(args.input)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = _rebuild_assignment(build_payload(mk_path))
    _assert_sanity(payload)
    out_path = output_dir / f"{payload['instance_name']}.json"
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    inst = load_mvc_instance_json(out_path)
    validate_mvc_instance(inst)
    total_ops = sum(int(j["n_operations"]) for j in payload["jobs"])
    rows = [
        {
            "instance": payload["instance_name"],
            "source_instance": payload["source_instance"],
            "jobs": payload["n_jobs"],
            "base_machines": payload["n_base_machines"],
            "value_chains": payload["n_value_chains"],
            "types": payload["n_types"],
            "srus": payload["n_srus"],
            "ops": total_ops,
            "seed": payload["seed"],
            "file": out_path.as_posix(),
        }
    ]
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["instance", "source_instance", "jobs", "base_machines", "value_chains", "types", "srus", "ops", "seed", "file"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    _write_readme(output_dir)
    print("validation: PASSED")
    print(f"output_file: {out_path.as_posix()}")
    print(f"manifest: {(output_dir / 'manifest.csv').as_posix()}")


if __name__ == "__main__":
    main()
