from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.data.mk_parser import MKInstance, parse_mk_file
from smdfjsp.data.mvc_io import load_mvc_instance_json, validate_mvc_instance


N_VALUE_CHAINS = 3
N_TYPES = 2
N_SRUS = 6
SEED = 20260611
MACHINE_COST_MIN = 5.0
MACHINE_COST_MAX = 12.0

SRU_SPECS: List[Tuple[str, str, str]] = [
    ("U1", "VC1", "T1"),
    ("U2", "VC1", "T2"),
    ("U3", "VC2", "T1"),
    ("U4", "VC2", "T2"),
    ("U5", "VC3", "T1"),
    ("U6", "VC3", "T2"),
]

SYMMETRIC_PAIR_PENALTIES: Dict[Tuple[str, str], dict] = {
    ("VC1", "VC2"): {
        "cross_chain_fixed_cost": 200.0,
        "cross_chain_cost_rate": 0.0,
        "transport_time_base": 7,
        "transport_unit_cost": 4.8,
    },
    ("VC2", "VC3"): {
        "cross_chain_fixed_cost": 230.0,
        "cross_chain_cost_rate": 0.0,
        "transport_time_base": 7,
        "transport_unit_cost": 5.1,
    },
    ("VC1", "VC3"): {
        "cross_chain_fixed_cost": 320.0,
        "cross_chain_cost_rate": 0.0,
        "transport_time_base": 10,
        "transport_unit_cost": 6.5,
    },
}


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _split_balanced(ids: List[int], n_groups: int) -> Dict[str, List[int]]:
    groups = {f"VC{i + 1}": [] for i in range(n_groups)}
    for pos, item in enumerate(ids):
        groups[f"VC{pos % n_groups + 1}"].append(item)
    return groups


def _assign_types_by_operation_count(mk: MKInstance, n_types: int) -> Dict[str, List[int]]:
    ordered = sorted(mk.jobs, key=lambda j: (len(j.operations), j.job_id))
    groups = {f"T{i + 1}": [] for i in range(n_types)}
    for pos, job in enumerate(ordered):
        groups[f"T{pos * n_types // max(len(ordered), 1) + 1}"].append(job.job_id)
    return {k: sorted(v) for k, v in groups.items()}


def _job_lookup(groups: Dict[str, List[int]]) -> Dict[int, str]:
    return {job_id: label for label, jobs in groups.items() for job_id in jobs}


def _machine_mean_times(mk: MKInstance) -> Dict[int, float]:
    values: Dict[int, List[int]] = {mid: [] for mid in range(mk.num_machines)}
    for job in mk.jobs:
        for op in job.operations:
            for machine_id_1based, process_time in op.options:
                values[machine_id_1based - 1].append(int(process_time))
    return {mid: sum(times) / len(times) for mid, times in values.items() if times}


def _machine_costs(mk: MKInstance) -> Dict[int, float]:
    means = _machine_mean_times(mk)
    fallback_mean = sum(means.values()) / max(len(means), 1)
    low = min(means.values())
    high = max(means.values())
    span = high - low
    costs: Dict[int, float] = {}
    for mid in range(mk.num_machines):
        mean_time = means.get(mid, fallback_mean)
        if span <= 0:
            cost = (MACHINE_COST_MIN + MACHINE_COST_MAX) / 2.0
        else:
            cost = MACHINE_COST_MIN + (MACHINE_COST_MAX - MACHINE_COST_MIN) * (high - mean_time) / span
        costs[mid] = float(round(cost, 2))
    return costs


def _pair_key(vc_a: str, vc_b: str) -> Tuple[str, str]:
    return tuple(sorted((vc_a, vc_b)))  # type: ignore[return-value]


def _cross_penalty(job_vc: str, sru_vc: str) -> dict:
    return SYMMETRIC_PAIR_PENALTIES[_pair_key(job_vc, sru_vc)]


def build_payload(mk_path: Path) -> dict:
    mk = parse_mk_file(mk_path)
    job_ids = [job.job_id for job in mk.jobs]
    value_chains = _split_balanced(job_ids, N_VALUE_CHAINS)
    types = _assign_types_by_operation_count(mk, N_TYPES)
    job_to_vc = _job_lookup(value_chains)
    job_to_type = _job_lookup(types)
    machine_costs = _machine_costs(mk)

    sru_to_vc = {sid: vc for sid, vc, _ in SRU_SPECS}
    candidate_srus_by_type = {
        "T1": ["U1", "U3", "U5"],
        "T2": ["U2", "U4", "U6"],
    }

    srus = []
    for sid, vc, typ in SRU_SPECS:
        srus.append(
            {
                "id": sid,
                "value_chain": vc,
                "type": typ,
                "open_to_cross_chain": True,
                "efficiency_factor": 1.0,
                "cost_factor": 1.0,
                "homogeneous_processing_time": True,
                "homogeneous_processing_cost": True,
                "machines": [
                    {
                        "local_machine_id": f"M{mid}",
                        "global_machine_id": f"{sid}_M{mid}",
                        "base_machine_id": mid,
                        "unit_processing_cost": machine_costs[mid],
                    }
                    for mid in range(mk.num_machines)
                ],
            }
        )

    jobs_payload: List[dict] = []
    compatibility: Dict[str, dict] = {}
    for mk_job in mk.jobs:
        jid = mk_job.job_id
        vc = job_to_vc[jid]
        typ = job_to_type[jid]
        all_type_srus = candidate_srus_by_type[typ]
        intra = [sid for sid in all_type_srus if sru_to_vc[sid] == vc]
        cross = [sid for sid in all_type_srus if sru_to_vc[sid] != vc]
        candidates = intra + cross

        operations: List[dict] = []
        for op_idx, mk_op in enumerate(mk_job.operations, start=1):
            eligible = [
                {"base_machine_id": int(machine_id_1based - 1), "base_processing_time": int(process_time)}
                for machine_id_1based, process_time in mk_op.options
            ]
            proc_by_sru: Dict[str, List[dict]] = {}
            for sid in candidates:
                proc_by_sru[sid] = [
                    {
                        "global_machine_id": f"{sid}_M{item['base_machine_id']}",
                        "base_machine_id": int(item["base_machine_id"]),
                        "base_processing_time": int(item["base_processing_time"]),
                        "adjusted_processing_time": int(item["base_processing_time"]),
                        "unit_processing_cost": machine_costs[int(item["base_machine_id"])],
                    }
                    for item in eligible
                ]
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
                "type": typ,
                "release_time": 0,
                "n_operations": len(mk_job.operations),
                "candidate_srus": candidates,
                "operations": operations,
            }
        )
        compatibility[f"J{jid}"] = {
            "candidate_srus": candidates,
            "intra_chain_srus": intra,
            "cross_chain_srus": cross,
        }

    transport_time: Dict[str, Dict[str, int]] = {}
    transport_cost: Dict[str, Dict[str, float]] = {}
    cross_chain: Dict[str, Dict[str, dict]] = {}
    for job in jobs_payload:
        jid = int(job["job_id"])
        jkey = f"J{jid}"
        job_vc = str(job["value_chain"])
        transport_time[jkey] = {}
        transport_cost[jkey] = {}
        cross_chain[jkey] = {}
        for sid in job["candidate_srus"]:
            sru_vc = sru_to_vc[sid]
            is_cross = job_vc != sru_vc
            if is_cross:
                penalty = _cross_penalty(job_vc, sru_vc)
                t = int(penalty["transport_time_base"] + jid % 3)
                fixed = float(penalty["cross_chain_fixed_cost"])
                rate = 0.0
                unit_transport_cost = float(penalty["transport_unit_cost"])
                estimated_cross = fixed
            else:
                t = int(2 + jid % 2)
                fixed = 0.0
                rate = 0.0
                unit_transport_cost = 1.8
                estimated_cross = 0.0

            transport_time[jkey][sid] = t
            transport_cost[jkey][sid] = float(round(t * unit_transport_cost, 6))
            cross_chain[jkey][sid] = {
                "job_value_chain": job_vc,
                "sru_value_chain": sru_vc,
                "is_cross_chain": bool(is_cross),
                "cross_chain_fixed_cost": float(round(fixed, 6)),
                "cross_chain_cost_rate": float(round(rate, 6)),
                "estimated_cross_chain_cost": float(round(estimated_cross, 6)),
            }

    pair_notes = {
        f"{a}-{b}": {
            "cross_chain_fixed_cost": values["cross_chain_fixed_cost"],
            "cross_chain_cost_rate": values["cross_chain_cost_rate"],
            "transport_time_base": values["transport_time_base"],
            "transport_unit_cost": values["transport_unit_cost"],
        }
        for (a, b), values in SYMMETRIC_PAIR_PENALTIES.items()
    }
    return {
        "instance_name": f"{mk.name}_mvc_3vc_2type_6sru_equalproc_vcpenalty",
        "source_instance": mk.name,
        "problem_type": "MVC-SM-DFJSP",
        "is_dynamic": False,
        "release_time_policy": "all_zero",
        "seed": SEED,
        "n_jobs": mk.num_jobs,
        "n_base_machines": mk.num_machines,
        "n_value_chains": N_VALUE_CHAINS,
        "n_types": N_TYPES,
        "n_srus": N_SRUS,
        "value_chains": [
            {"id": label, "name": f"Value chain {label.replace('VC', '')}", "jobs": jobs}
            for label, jobs in value_chains.items()
        ],
        "types": [
            {"id": label, "name": f"Service type {label.replace('T', '')}", "jobs": jobs}
            for label, jobs in types.items()
        ],
        "base_machines": [
            {"local_machine_id": f"M{mid}", "base_machine_id": mid, "base_unit_processing_cost": machine_costs[mid]}
            for mid in range(mk.num_machines)
        ],
        "jobs": jobs_payload,
        "srus": srus,
        "candidate_srus_by_type": candidate_srus_by_type,
        "job_sru_compatibility": compatibility,
        "transport_time": transport_time,
        "transport_cost": transport_cost,
        "cross_chain": cross_chain,
        "objectives": [
            {"id": "total_cost", "sense": "min", "definition": "PC + TC + CFC"},
            {"id": "makespan", "sense": "min", "definition": "max(C_j + transport_time)"},
        ],
        "diagnostics": ["max_sru_load", "sru_load_std", "cross_chain_ratio", "cross_chain_flow"],
        "notes": {
            "source_mk_file": str(mk_path.as_posix()),
            "static_orders_only": True,
            "all_release_time_zero": True,
            "job_single_sru_hard_constraint": True,
            "operations_keep_original_order": True,
            "all_srus_open_to_cross_chain": True,
            "cross_chain_allowed_is_experiment_mode": True,
            "processing_time_rule": "adjusted_processing_time equals original MK base_processing_time for every SRU.",
            "processing_cost_rule": "unit_processing_cost depends only on base_machine_id and is identical across all SRUs.",
            "machine_cost_rule": "Machine cost is inverse-normalized from the source MK instance mean processing time to [5.0, 12.0], rounded to 2 decimals.",
            "local_transport_rule": "transport_time = 2 + job_id % 2; transport_unit_cost = 1.8.",
            "cross_chain_penalty_rule": "3VC symmetric fixed cross-chain penalty; variable rate is always 0.",
            "symmetric_cross_chain_penalty_by_vc_pair": pair_notes,
            "cross_chain_cost_rule": "fixed_only_no_variable_rate",
        },
    }


def _assert_sanity(payload: dict) -> None:
    pair_fixed = {
        pair: float(values["cross_chain_fixed_cost"])
        for pair, values in payload["notes"]["symmetric_cross_chain_penalty_by_vc_pair"].items()
    }
    for job in payload["jobs"]:
        comp = payload["job_sru_compatibility"][f"J{job['job_id']}"]
        if len(comp["candidate_srus"]) != 3 or len(comp["intra_chain_srus"]) != 1 or len(comp["cross_chain_srus"]) != 2:
            raise AssertionError(f"Unexpected candidate split for J{job['job_id']}: {comp}")
        for op in job["operations"]:
            eligible = {int(item["base_machine_id"]): int(item["base_processing_time"]) for item in op["eligible_base_machines"]}
            signatures = []
            for sid, options in op["processing_options_by_sru"].items():
                sig = []
                for item in options:
                    base_mid = int(item["base_machine_id"])
                    if int(item["adjusted_processing_time"]) != eligible[base_mid]:
                        raise AssertionError(f"{sid} adjusted time differs from base time")
                    sig.append((base_mid, int(item["adjusted_processing_time"]), float(item["unit_processing_cost"])))
                signatures.append(tuple(sig))
            if len(set(signatures)) != 1:
                raise AssertionError("Processing options are not identical across candidate SRUs")
    for jkey, by_sru in payload["cross_chain"].items():
        for sid, info in by_sru.items():
            if float(info["cross_chain_cost_rate"]) != 0.0:
                raise AssertionError(f"{jkey}-{sid} has non-zero cross_chain_cost_rate")
            if info["is_cross_chain"]:
                pair = "-".join(sorted((str(info["job_value_chain"]), str(info["sru_value_chain"]))))
                expected = pair_fixed[pair]
            else:
                expected = 0.0
            if float(info["cross_chain_fixed_cost"]) != expected:
                raise AssertionError(f"{jkey}-{sid} fixed cost mismatch")


def _write_readme(output_dir: Path) -> None:
    text = """# MVC MK14-MK15 Merged 3VC/2Type/6SRU Equal-Processing Dataset

Generated from `data/mk/mk14_mk15_merged.txt` using the same equal-processing and fixed cross-chain penalty policy as `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`, extended to 3 value chains and 6 SRUs.

- Value chains: VC1, VC2, VC3 are assigned by job-id round robin.
- Service types: T1/T2 are assigned by operation-count split.
- SRUs: U1=VC1-T1, U2=VC1-T2, U3=VC2-T1, U4=VC2-T2, U5=VC3-T1, U6=VC3-T2.
- Each job has exactly one intra-chain SRU and two cross-chain SRUs with matching service type.
- Processing time is homogeneous across candidate SRUs: adjusted_processing_time equals the original MK processing time.
- Unit processing cost depends only on the base machine and is identical across SRUs.
- Local transport: transport_time = 2 + job_id % 2, transport_unit_cost = 1.8.
- Cross-chain transport: VC1-VC2 and VC2-VC3 use base time 7; VC1-VC3 uses base time 10; then add job_id % 3.
- Cross-chain fixed costs: VC1-VC2=200.0, VC2-VC3=230.0, VC1-VC3=320.0.
- cross_chain_cost_rate is always 0.0.
- Formal total cost: processing_cost + transport_cost + cross_fixed_cost.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the merged MK14+MK15 source as a 3VC/2type/6SRU equal-processing MVC instance.")
    parser.add_argument("--input", default="data/mk/mk14_mk15_merged.txt")
    parser.add_argument("--output-dir", default="data/mvc_mk_merged_3vc6sru_equalproc_vcpenalty")
    args = parser.parse_args()

    mk_path = _resolve(args.input)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payload = build_payload(mk_path)
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
    print(f"built_instances: {len(rows)}")
    print(f"output_file: {out_path.as_posix()}")
    print(f"manifest: {(output_dir / 'manifest.csv').as_posix()}")


if __name__ == "__main__":
    main()
