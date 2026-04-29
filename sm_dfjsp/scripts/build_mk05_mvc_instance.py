from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


@dataclass
class MKOperation:
    options: List[Tuple[int, int]]  # (global_machine_id_1based, process_time)


@dataclass
class MKJob:
    job_id: int
    operations: List[MKOperation]


@dataclass
class MKInstance:
    name: str
    num_jobs: int
    num_machines: int
    jobs: List[MKJob]


def parse_mk_file(path: str | Path) -> MKInstance:
    path = Path(path)
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    head = [int(x) for x in lines[0].split()]
    num_jobs, num_machines = head[0], head[1]
    jobs: List[MKJob] = []
    for j_idx in range(num_jobs):
        tokens = [int(x) for x in lines[j_idx + 1].split()]
        cursor = 0
        op_count = tokens[cursor]
        cursor += 1
        operations: List[MKOperation] = []
        for _ in range(op_count):
            option_count = tokens[cursor]
            cursor += 1
            options: List[Tuple[int, int]] = []
            for _ in range(option_count):
                machine_zero_based = tokens[cursor]
                process_time = tokens[cursor + 1]
                cursor += 2
                options.append((machine_zero_based + 1, process_time))
            operations.append(MKOperation(options=options))
        jobs.append(MKJob(job_id=j_idx + 1, operations=operations))
    return MKInstance(
        name=path.stem.lower(),
        num_jobs=num_jobs,
        num_machines=num_machines,
        jobs=jobs,
    )


VALUE_CHAINS: Dict[str, List[int]] = {
    "VC1": [1, 2, 3, 4, 5],
    "VC2": [6, 7, 8, 9, 10],
    "VC3": [11, 12, 13, 14, 15],
}

TYPES: Dict[str, List[int]] = {
    # Two-type partition by process length on MK05:
    # T1: short-process jobs (<= 6 operations)
    # T2: medium/long-process jobs (>= 7 operations)
    "T1": [1, 2, 5, 7, 12],
    "T2": [3, 4, 6, 8, 9, 10, 11, 13, 14, 15],
}

TYPE_NAMES: Dict[str, str] = {
    "T1": "短流程件",
    "T2": "中长流程件",
}

SRU_SPECS = [
    ("U1", "VC1", "T1", 1.00, 1.00),
    ("U2", "VC1", "T2", 0.95, 1.10),
    ("U3", "VC2", "T1", 0.90, 1.20),
    ("U4", "VC2", "T2", 1.05, 0.95),
    ("U5", "VC3", "T2", 0.92, 1.15),
    ("U6", "VC3", "T1", 1.10, 0.90),
]

CANDIDATE_SRUS_BY_TYPE: Dict[str, List[str]] = {
    "T1": ["U1", "U3", "U6"],
    "T2": ["U2", "U4", "U5"],
}

BASE_MACHINE_COST = {0: 6.0, 1: 5.0, 2: 7.0, 3: 8.0}

BASE_TRANSPORT_TIME = {
    "VC1": {"VC1": 3, "VC2": 9, "VC3": 12},
    "VC2": {"VC1": 10, "VC2": 3, "VC3": 8},
    "VC3": {"VC1": 11, "VC2": 7, "VC3": 3},
}

UNIT_TRANSPORT_COST = 3.0


def _resolve_input(input_path: Path) -> Path:
    if input_path.exists():
        return input_path
    if input_path.as_posix().endswith("data/fjsp/mk05.txt"):
        alt = input_path.parents[1] / "mk05.txt"
        if alt.exists():
            return alt
    raise FileNotFoundError(f"Input mk file not found: {input_path}")


def _job_to_value_chain(job_id: int) -> str:
    for vc, jobs in VALUE_CHAINS.items():
        if job_id in jobs:
            return vc
    raise AssertionError(f"Job {job_id} not found in any value chain.")


def _job_to_type(job_id: int) -> str:
    for t, jobs in TYPES.items():
        if job_id in jobs:
            return t
    raise AssertionError(f"Job {job_id} not found in any type.")


def _build_sru_payload() -> Tuple[List[dict], Dict[str, dict], Dict[str, str], Dict[str, str]]:
    srus: List[dict] = []
    sru_map: Dict[str, dict] = {}
    sru_to_vc: Dict[str, str] = {}
    sru_to_type: Dict[str, str] = {}
    for sru_id, vc, t, eff, cost_factor in SRU_SPECS:
        machines = []
        for base_mid in range(4):
            local_id = f"M{base_mid}"
            unit_cost = BASE_MACHINE_COST[base_mid] * cost_factor
            machines.append(
                {
                    "local_machine_id": local_id,
                    "global_machine_id": f"{sru_id}_{local_id}",
                    "base_machine_id": base_mid,
                    "unit_processing_cost": float(round(unit_cost, 6)),
                }
            )
        sru_obj = {
            "id": sru_id,
            "value_chain": vc,
            "type": t,
            "efficiency_factor": float(eff),
            "cost_factor": float(cost_factor),
            "machines": machines,
        }
        srus.append(sru_obj)
        sru_map[sru_id] = sru_obj
        sru_to_vc[sru_id] = vc
        sru_to_type[sru_id] = t
    return srus, sru_map, sru_to_vc, sru_to_type


def _build_jobs_and_compatibility(
    mk: MKInstance,
    rng: np.random.Generator,
    sru_map: Dict[str, dict],
    sru_to_vc: Dict[str, str],
) -> Tuple[List[dict], Dict[str, dict]]:
    jobs_payload: List[dict] = []
    compatibility: Dict[str, dict] = {}

    for job in mk.jobs:
        jid = int(job.job_id)
        job_key = f"J{jid}"
        vc = _job_to_value_chain(jid)
        t = _job_to_type(jid)
        candidate_srus = list(CANDIDATE_SRUS_BY_TYPE[t])
        intra = [u for u in candidate_srus if sru_to_vc[u] == vc]
        cross = [u for u in candidate_srus if sru_to_vc[u] != vc]
        compatibility[job_key] = {
            "candidate_srus": candidate_srus,
            "intra_chain_srus": intra,
            "cross_chain_srus": cross,
        }

        operations: List[dict] = []
        for op_idx, op in enumerate(job.operations, start=1):
            eligible = []
            for mid_1b, pt in op.options:
                eligible.append({"base_machine_id": int(mid_1b - 1), "base_processing_time": int(pt)})

            proc_by_sru: Dict[str, List[dict]] = {}
            for sru_id in candidate_srus:
                sru = sru_map[sru_id]
                eff = float(sru["efficiency_factor"])
                options = []
                for item in eligible:
                    base_mid = int(item["base_machine_id"])
                    base_pt = int(item["base_processing_time"])
                    noise = float(rng.uniform(0.95, 1.05))
                    adjusted = int(math.ceil(base_pt * eff * noise))
                    adjusted = max(1, adjusted)
                    machine_obj = sru["machines"][base_mid]
                    options.append(
                        {
                            "global_machine_id": machine_obj["global_machine_id"],
                            "base_machine_id": base_mid,
                            "base_processing_time": base_pt,
                            "adjusted_processing_time": adjusted,
                            "unit_processing_cost": float(machine_obj["unit_processing_cost"]),
                        }
                    )
                proc_by_sru[sru_id] = options

            operations.append(
                {
                    "op_id": op_idx,
                    "op_id_zero_based": op_idx - 1,
                    "eligible_base_machines": eligible,
                    "processing_options_by_sru": proc_by_sru,
                }
            )

        jobs_payload.append(
            {
                "job_id": jid,
                "job_id_zero_based": jid - 1,
                "value_chain": vc,
                "type": t,
                "release_time": 0,
                "n_operations": len(job.operations),
                "candidate_srus": candidate_srus,
                "operations": operations,
            }
        )
    return jobs_payload, compatibility


def _build_transport_and_cross_chain(
    jobs_payload: List[dict],
    sru_to_vc: Dict[str, str],
    rng: np.random.Generator,
) -> Tuple[Dict[str, Dict[str, int]], Dict[str, Dict[str, float]], Dict[str, Dict[str, dict]]]:
    transport_time: Dict[str, Dict[str, int]] = {}
    transport_cost: Dict[str, Dict[str, float]] = {}
    cross_chain: Dict[str, Dict[str, dict]] = {}

    for job in jobs_payload:
        jkey = f"J{job['job_id']}"
        job_vc = str(job["value_chain"])
        transport_time[jkey] = {}
        transport_cost[jkey] = {}
        cross_chain[jkey] = {}
        for sru_id in job["candidate_srus"]:
            sru_vc = sru_to_vc[sru_id]
            base_t = int(BASE_TRANSPORT_TIME[job_vc][sru_vc])
            noise = int(rng.integers(0, 3))
            t = int(base_t + noise)
            c = float(t * UNIT_TRANSPORT_COST)
            transport_time[jkey][sru_id] = t
            transport_cost[jkey][sru_id] = c

            is_cross = job_vc != sru_vc
            if is_cross:
                est_proc = 0.0
                for op in job["operations"]:
                    opts = op["processing_options_by_sru"][sru_id]
                    min_cost = min(float(x["adjusted_processing_time"]) * float(x["unit_processing_cost"]) for x in opts)
                    est_proc += min_cost
                estimated = 20.0 + 0.05 * est_proc
                cross_chain[jkey][sru_id] = {
                    "job_value_chain": job_vc,
                    "sru_value_chain": sru_vc,
                    "is_cross_chain": True,
                    "cross_chain_fixed_cost": 20.0,
                    "cross_chain_cost_rate": 0.05,
                    "estimated_cross_chain_cost": float(round(estimated, 6)),
                }
            else:
                cross_chain[jkey][sru_id] = {
                    "job_value_chain": job_vc,
                    "sru_value_chain": sru_vc,
                    "is_cross_chain": False,
                    "cross_chain_fixed_cost": 0.0,
                    "cross_chain_cost_rate": 0.0,
                    "estimated_cross_chain_cost": 0.0,
                }

    return transport_time, transport_cost, cross_chain


def _validate_instance(
    data: dict,
    mk: MKInstance,
    sru_to_type: Dict[str, str],
) -> None:
    assert data["n_jobs"] == 15, "Validation failed: n_jobs must be 15."
    assert data["n_base_machines"] == 4, "Validation failed: n_base_machines must be 4."
    assert data["n_value_chains"] == 3, "Validation failed: n_value_chains must be 3."
    assert data["n_types"] == 2, "Validation failed: n_types must be 2."
    assert data["n_srus"] == 6, "Validation failed: n_srus must be 6."

    for job in data["jobs"]:
        assert int(job["release_time"]) == 0, f"Validation failed: {job['job_id']} release_time must be 0."

    for job in data["jobs"]:
        assert isinstance(job["value_chain"], str) and job["value_chain"].startswith("VC"), "Validation failed: invalid value_chain."
        assert isinstance(job["type"], str) and job["type"].startswith("T"), "Validation failed: invalid type."

    for job in data["jobs"]:
        jid = int(job["job_id"])
        assert len(job["candidate_srus"]) >= 1, f"Validation failed: J{jid} has no candidate SRU."
        for sru_id in job["candidate_srus"]:
            assert sru_to_type[sru_id] == job["type"], (
                f"Validation failed: J{jid} candidate {sru_id} type mismatch "
                f"({sru_to_type[sru_id]} != {job['type']})."
            )
        intra = data["job_sru_compatibility"][f"J{jid}"]["intra_chain_srus"]
        assert intra, f"Validation failed: J{jid} has no same-value-chain same-type SRU."

    for job in data["jobs"]:
        cand = set(job["candidate_srus"])
        for op in job["operations"]:
            seen = set(op["processing_options_by_sru"].keys())
            assert seen.issubset(cand), (
                f"Validation failed: J{job['job_id']} op{op['op_id']} has non-candidate SRU options."
            )

    for sru in data["srus"]:
        assert len(sru["machines"]) == 4, f"Validation failed: {sru['id']} must have 4 machines."

    mk_job_map = {j.job_id: j for j in mk.jobs}
    for job in data["jobs"]:
        jid = int(job["job_id"])
        original_job = mk_job_map[jid]
        assert len(job["operations"]) == len(original_job.operations), (
            f"Validation failed: J{jid} op count mismatch with mk."
        )
        for op in job["operations"]:
            op_idx = int(op["op_id"]) - 1
            original_op = original_job.operations[op_idx]
            original = [(m - 1, t) for m, t in original_op.options]
            now = [(int(x["base_machine_id"]), int(x["base_processing_time"])) for x in op["eligible_base_machines"]]
            assert original == now, (
                f"Validation failed: J{jid} op{op['op_id']} eligible_base_machines mismatch with mk."
            )

            expected = len(op["eligible_base_machines"])
            for sru_id, opts in op["processing_options_by_sru"].items():
                assert len(opts) == expected, (
                    f"Validation failed: J{jid} op{op['op_id']} {sru_id} option count mismatch."
                )
                for item in opts:
                    adj = int(item["adjusted_processing_time"])
                    assert adj > 0, f"Validation failed: adjusted_processing_time must be >0 at J{jid} op{op['op_id']}."

    for jkey, row in data["transport_time"].items():
        for sru_id, t in row.items():
            assert float(t) > 0, f"Validation failed: transport_time must be positive for {jkey}-{sru_id}."
    for jkey, row in data["transport_cost"].items():
        for sru_id, c in row.items():
            assert float(c) > 0, f"Validation failed: transport_cost must be positive for {jkey}-{sru_id}."

    for job in data["jobs"]:
        jkey = f"J{job['job_id']}"
        jvc = str(job["value_chain"])
        for sru_id in job["candidate_srus"]:
            rec = data["cross_chain"][jkey][sru_id]
            is_cross = bool(rec["is_cross_chain"])
            svc = str(rec["sru_value_chain"])
            if jvc == svc:
                assert not is_cross, f"Validation failed: {jkey}-{sru_id} should be intra-chain."
                assert float(rec["cross_chain_fixed_cost"]) == 0.0, "Validation failed: intra-chain fixed cost must be 0."
                assert float(rec["cross_chain_cost_rate"]) == 0.0, "Validation failed: intra-chain cost rate must be 0."
                assert float(rec["estimated_cross_chain_cost"]) == 0.0, "Validation failed: intra-chain estimated cost must be 0."
            else:
                assert is_cross, f"Validation failed: {jkey}-{sru_id} should be cross-chain."
                assert float(rec["cross_chain_fixed_cost"]) == 20.0, "Validation failed: cross-chain fixed cost must be 20."
                assert math.isclose(float(rec["cross_chain_cost_rate"]), 0.05), "Validation failed: cross-chain rate must be 0.05."

    for job in data["jobs"]:
        jkey = f"J{job['job_id']}"
        comp = data["job_sru_compatibility"][jkey]
        assert len(comp["intra_chain_srus"]) >= 1, (
            f"Validation failed: {jkey} must have at least one intra-chain same-type SRU."
        )


def _print_summary(data: dict) -> None:
    total_ops = sum(int(j["n_operations"]) for j in data["jobs"])
    print("=== MVC-SM-DFJSP Instance Summary ===")
    print(f"instance_name: {data['instance_name']}")
    print(f"n_jobs: {data['n_jobs']}")
    print(f"total_operations: {total_ops}")
    print(f"n_value_chains: {data['n_value_chains']}")
    print(f"n_types: {data['n_types']}")
    print(f"n_srus: {data['n_srus']}")

    print("\nvalue chains:")
    for vc in data["value_chains"]:
        print(f"  {vc['id']}: {vc['jobs']}")

    print("\ntypes:")
    for t in data["types"]:
        print(f"  {t['id']} ({t['name']}): {t['jobs']}")

    print("\ncandidate SRUs by type:")
    for t, srus in data["candidate_srus_by_type"].items():
        print(f"  {t}: {srus}")

    print("\nSRUs:")
    for sru in data["srus"]:
        print(
            f"  {sru['id']}: vc={sru['value_chain']}, type={sru['type']}, "
            f"machines={len(sru['machines'])}, eff={sru['efficiency_factor']}, cost_factor={sru['cost_factor']}"
        )

    print("\njob compatibility:")
    must_cross = []
    for job in data["jobs"]:
        jkey = f"J{job['job_id']}"
        comp = data["job_sru_compatibility"][jkey]
        print(
            f"  {jkey}: candidate={comp['candidate_srus']}, "
            f"intra={comp['intra_chain_srus']}, cross={comp['cross_chain_srus']}"
        )
        if len(comp["intra_chain_srus"]) == 0:
            must_cross.append(jkey)

    print("\nmust cross-chain jobs:")
    print(f"  {must_cross}")


def build_instance(input_path: Path, output_path: Path, seed: int) -> dict:
    mk_path = _resolve_input(input_path)
    mk = parse_mk_file(mk_path)
    rng = np.random.default_rng(seed)

    srus, sru_map, sru_to_vc, sru_to_type = _build_sru_payload()
    jobs_payload, compatibility = _build_jobs_and_compatibility(mk, rng, sru_map, sru_to_vc)
    transport_time, transport_cost, cross_chain = _build_transport_and_cross_chain(jobs_payload, sru_to_vc, rng)

    value_chains_payload = [
        {"id": "VC1", "name": "价值链1", "jobs": VALUE_CHAINS["VC1"]},
        {"id": "VC2", "name": "价值链2", "jobs": VALUE_CHAINS["VC2"]},
        {"id": "VC3", "name": "价值链3", "jobs": VALUE_CHAINS["VC3"]},
    ]
    types_payload = [{"id": t, "name": TYPE_NAMES[t], "jobs": TYPES[t]} for t in ["T1", "T2"]]

    base_machines = [
        {"local_machine_id": f"M{i}", "base_machine_id": i, "base_unit_processing_cost": BASE_MACHINE_COST[i]}
        for i in range(mk.num_machines)
    ]

    data = {
        "instance_name": "mk05_mvc_3vc_2type_6sru",
        "source_instance": "mk05",
        "problem_type": "MVC-SM-DFJSP",
        "is_dynamic": False,
        "release_time_policy": "all_zero",
        "seed": int(seed),
        "n_jobs": int(mk.num_jobs),
        "n_base_machines": int(mk.num_machines),
        "n_value_chains": 3,
        "n_types": 2,
        "n_srus": 6,
        "value_chains": value_chains_payload,
        "types": types_payload,
        "base_machines": base_machines,
        "jobs": jobs_payload,
        "srus": srus,
        "candidate_srus_by_type": CANDIDATE_SRUS_BY_TYPE,
        "job_sru_compatibility": compatibility,
        "transport_time": transport_time,
        "transport_cost": transport_cost,
        "cross_chain": cross_chain,
        "objectives": [
            {
                "id": "total_cost",
                "sense": "min",
                "definition": "processing_cost + transport_cost + cross_chain_collaboration_cost",
            },
            {
                "id": "makespan",
                "sense": "min",
                "definition": "max(job_completion_time + transport_time)",
            },
            {
                "id": "sru_load_imbalance",
                "sense": "min",
                "definition": "standard_deviation_or_range_of_sru_workloads",
            },
        ],
        "notes": {
            "source_mk_file": str(mk_path.as_posix()),
            "static_orders_only": True,
            "all_release_time_zero": True,
            "job_single_sru_hard_constraint": True,
            "operations_keep_original_order": True,
            "sru_machine_replicas": "Each SRU contains local copies of M0..M3",
            "transport_unit_cost": UNIT_TRANSPORT_COST,
        },
    }

    _validate_instance(data, mk, sru_to_type)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="data/fjsp/mk05.txt")
    parser.add_argument("--output", default="data/mvc_sm_dfjsp/mk05_mvc_3vc_6sru.json")
    parser.add_argument("--seed", type=int, default=20260428)
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    input_path = root / args.input
    output_path = root / args.output

    data = build_instance(input_path=input_path, output_path=output_path, seed=int(args.seed))
    _print_summary(data)
    print(f"\noutput_json: {output_path.as_posix()}")
    print("validation: PASSED")


if __name__ == "__main__":
    main()
