from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.data.mk_parser import MKInstance, parse_mk_file
from smdfjsp.data.mvc_io import load_mvc_instance_json, validate_mvc_instance


N_VALUE_CHAINS = 2
N_TYPES = 2
N_SRUS = 8
SEED = 20260630
VC1_LOAD_RATIO = 0.70
MACHINE_COST_MIN = 5.0
MACHINE_COST_MAX = 12.0

SRU_SPECS: List[Tuple[str, str, str]] = [
    ("U1", "VC1", "T1"),
    ("U5", "VC1", "T1"),
    ("U2", "VC1", "T2"),
    ("U6", "VC1", "T2"),
    ("U3", "VC2", "T1"),
    ("U7", "VC2", "T1"),
    ("U4", "VC2", "T2"),
    ("U8", "VC2", "T2"),
]

CANDIDATE_SRUS_BY_TYPE = {
    "T1": ["U1", "U5", "U3", "U7"],
    "T2": ["U2", "U6", "U4", "U8"],
}


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _assign_types_by_operation_count(mk: MKInstance, n_types: int) -> Dict[str, List[int]]:
    ordered = sorted(mk.jobs, key=lambda j: (len(j.operations), j.job_id))
    groups = {f"T{i + 1}": [] for i in range(n_types)}
    for pos, job in enumerate(ordered):
        groups[f"T{pos * n_types // max(len(ordered), 1) + 1}"].append(job.job_id)
    return {k: sorted(v) for k, v in groups.items()}


def _job_lookup(groups: Dict[str, List[int]]) -> Dict[int, str]:
    return {job_id: label for label, jobs in groups.items() for job_id in jobs}


def _job_workload_by_id(mk: MKInstance) -> Dict[int, float]:
    workloads: Dict[int, float] = {}
    for job in mk.jobs:
        workloads[job.job_id] = float(sum(min(process_time for _, process_time in op.options) for op in job.operations))
    return workloads


def _assign_integrated_value_chains(mk: MKInstance, types: Dict[str, List[int]], ratio: float) -> Dict[str, List[int]]:
    workloads = _job_workload_by_id(mk)
    value_chains = {"VC1": [], "VC2": []}
    for job_ids in types.values():
        ordered = sorted(job_ids, key=lambda job_id: (-workloads[job_id], job_id))
        vc1_count = min(len(ordered) - 1, max(1, int(math.ceil(len(ordered) * ratio))))
        for pos, job_id in enumerate(ordered):
            value_chains["VC1" if pos < vc1_count else "VC2"].append(job_id)
    return {label: sorted(job_ids) for label, job_ids in value_chains.items()}


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


def _ordered_candidates(type_label: str, job_vc: str, sru_to_vc: Dict[str, str]) -> tuple[List[str], List[str], List[str]]:
    same_type = CANDIDATE_SRUS_BY_TYPE[type_label]
    intra = [sid for sid in same_type if sru_to_vc[sid] == job_vc]
    cross = [sid for sid in same_type if sru_to_vc[sid] != job_vc]
    return intra + cross, intra, cross


def _sru_payloads(mk: MKInstance, machine_costs: Dict[int, float]) -> List[dict]:
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
    return srus


def _type_summary(mk: MKInstance, types: Dict[str, List[int]], value_chains: Dict[str, List[int]]) -> Dict[str, dict]:
    workloads = _job_workload_by_id(mk)
    vc_sets = {vc: set(job_ids) for vc, job_ids in value_chains.items()}
    summary: Dict[str, dict] = {}
    for type_label, job_ids in sorted(types.items()):
        total_workload = sum(workloads[job_id] for job_id in job_ids)
        item: Dict[str, object] = {"jobs": len(job_ids), "total_workload": round(total_workload, 6)}
        for vc in ("VC1", "VC2"):
            vc_jobs = [job_id for job_id in job_ids if job_id in vc_sets[vc]]
            vc_workload = sum(workloads[job_id] for job_id in vc_jobs)
            item[f"{vc}_jobs"] = len(vc_jobs)
            item[f"{vc}_workload"] = round(vc_workload, 6)
            item[f"{vc}_workload_share"] = round(vc_workload / total_workload, 6) if total_workload else 0.0
        summary[type_label] = item
    return summary


def build_payload(mk_path: Path, ratio: float = VC1_LOAD_RATIO) -> dict:
    mk = parse_mk_file(mk_path)
    types = _assign_types_by_operation_count(mk, N_TYPES)
    value_chains = _assign_integrated_value_chains(mk, types, ratio)
    job_to_type = _job_lookup(types)
    job_to_vc = _job_lookup(value_chains)
    machine_costs = _machine_costs(mk)
    sru_to_vc = {sid: vc for sid, vc, _ in SRU_SPECS}
    sru_to_type = {sid: typ for sid, _, typ in SRU_SPECS}

    jobs_payload: List[dict] = []
    compatibility: Dict[str, dict] = {}
    for mk_job in mk.jobs:
        jid = mk_job.job_id
        vc = job_to_vc[jid]
        typ = job_to_type[jid]
        candidates, intra, cross = _ordered_candidates(typ, vc, sru_to_vc)
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
                t = int(4 + jid % 2)
                fixed = 90.0
                unit_transport_cost = 3.5
            else:
                t = int(2 + jid % 2)
                fixed = 0.0
                unit_transport_cost = 1.8
            transport_time[jkey][sid] = t
            transport_cost[jkey][sid] = float(round(t * unit_transport_cost, 6))
            cross_chain[jkey][sid] = {
                "job_value_chain": job_vc,
                "sru_value_chain": sru_vc,
                "is_cross_chain": bool(is_cross),
                "cross_chain_fixed_cost": float(fixed),
                "cross_chain_cost_rate": 0.0,
                "estimated_cross_chain_cost": float(fixed),
            }

    return {
        "instance_name": f"{mk.name}_mvc_2vc_2type_8sru_integrated_mechanism",
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
        "srus": _sru_payloads(mk, machine_costs),
        "candidate_srus_by_type": CANDIDATE_SRUS_BY_TYPE,
        "job_sru_compatibility": compatibility,
        "transport_time": transport_time,
        "transport_cost": transport_cost,
        "cross_chain": cross_chain,
        "objectives": [
            {"id": "total_cost", "sense": "min", "definition": "PC + TC + CFC"},
            {"id": "makespan", "sense": "min", "definition": "max(C_j + transport_time)"},
        ],
        "diagnostics": ["max_sru_load", "sru_load_std", "cross_chain_ratio", "cross_chain_flow"],
        "mechanism_scenario": "integrated_mechanism",
        "notes": {
            "source_mk_file": str(mk_path.as_posix()),
            "mechanism_scenario": "integrated_mechanism",
            "mechanism_generated_by": "scripts/build_lamed_2vc8sru_integrated_mechanism_equalproc.py",
            "mechanism_design": (
                "High-workload jobs within each service type are assigned to VC1 with ratio=0.70, "
                "creating intra-chain congestion while keeping VC2 non-empty. Each value-chain/type "
                "cell has two same-type SRUs, so cross-off retains two intra-chain choices and cross-on "
                "adds two cross-chain relief SRUs."
            ),
            "value_chain_load_ratio_policy": "la31-la35 and sm03_1: top 70% workload jobs per type -> VC1.",
            "static_orders_only": True,
            "all_release_time_zero": True,
            "job_single_sru_hard_constraint": True,
            "operations_keep_original_order": True,
            "all_srus_open_to_cross_chain": True,
            "cross_chain_allowed_is_experiment_mode": True,
            "processing_time_consistency_rule": (
                "For every job, operation, and base_machine_id, adjusted_processing_time is identical across all candidate SRUs."
            ),
            "processing_cost_consistency_rule": (
                "For every job, operation, and base_machine_id, unit_processing_cost is identical across all candidate SRUs."
            ),
            "machine_cost_rule": (
                "Machine cost is inverse-normalized from source mean processing time to [5.0, 12.0], rounded to 2 decimals."
            ),
            "local_transport_rule": "transport_time = 2 + job_id % 2; transport_unit_cost = 1.8.",
            "cross_transport_time": "4 + job_id % 2",
            "cross_transport_unit_cost": 3.5,
            "cross_fixed_cost": 90.0,
            "cross_chain_cost_rule": "fixed_only_no_variable_rate",
        },
        "type_value_chain_summary": _type_summary(mk, types, value_chains),
    }


def _assert_sanity(payload: dict) -> None:
    if int(payload["n_srus"]) != 8:
        raise AssertionError("n_srus must be 8")
    if len(payload["srus"]) != 8:
        raise AssertionError("SRU list must contain 8 SRUs")
    sru_vc = {str(sru["id"]): str(sru["value_chain"]) for sru in payload["srus"]}
    for job in payload["jobs"]:
        job_id = int(job["job_id"])
        comp = payload["job_sru_compatibility"][f"J{job_id}"]
        if len(comp["intra_chain_srus"]) != 2 or len(comp["cross_chain_srus"]) != 2:
            raise AssertionError(f"Unexpected candidate split for J{job_id}: {comp}")
        if comp["candidate_srus"] != comp["intra_chain_srus"] + comp["cross_chain_srus"]:
            raise AssertionError(f"Candidate order mismatch for J{job_id}: {comp}")
        for sid in comp["candidate_srus"]:
            if sid not in payload["transport_time"][f"J{job_id}"]:
                raise AssertionError(f"Missing transport_time for J{job_id}-{sid}")
            if sid not in payload["cross_chain"][f"J{job_id}"]:
                raise AssertionError(f"Missing cross_chain metadata for J{job_id}-{sid}")
            info = payload["cross_chain"][f"J{job_id}"][sid]
            expected_cross = str(job["value_chain"]) != sru_vc[sid]
            if bool(info["is_cross_chain"]) != expected_cross:
                raise AssertionError(f"Wrong cross flag for J{job_id}-{sid}")
            expected_fixed = 90.0 if expected_cross else 0.0
            if float(info["cross_chain_fixed_cost"]) != expected_fixed:
                raise AssertionError(f"Wrong fixed cost for J{job_id}-{sid}")
            if float(info["cross_chain_cost_rate"]) != 0.0:
                raise AssertionError(f"Non-zero cross_chain_cost_rate for J{job_id}-{sid}")
        for op in job["operations"]:
            by_machine: Dict[int, List[Tuple[int, float]]] = {}
            for options in op["processing_options_by_sru"].values():
                for option in options:
                    by_machine.setdefault(int(option["base_machine_id"]), []).append(
                        (int(option["adjusted_processing_time"]), float(option["unit_processing_cost"]))
                    )
            for values in by_machine.values():
                if len(set(values)) != 1:
                    raise AssertionError(f"Inconsistent processing option in J{job_id}-O{op['op_id']}: {values}")


def _candidate_sanity(payload: dict) -> tuple[int, int]:
    intra_total = 0
    cross_total = 0
    for job in payload["jobs"]:
        comp = payload["job_sru_compatibility"][f"J{int(job['job_id'])}"]
        intra_total += len(comp["intra_chain_srus"])
        cross_total += len(comp["cross_chain_srus"])
    return intra_total, cross_total


def _write_payload(payload: dict, path: Path) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    inst = load_mvc_instance_json(path)
    validate_mvc_instance(inst)


def _write_readme(output_dir: Path) -> None:
    text = """# MVC-LAMED 2VC/2Type/8SRU Integrated Mechanism Equal-Processing Dataset

Generated from `data/lamed` using the integrated-mechanism construction policy
of `data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc`, extended to eight
SRUs so that cross-off keeps two intra-chain same-type choices per job.

## Source instances

- `la31-la35`: 30 jobs, 10 machines, 300 operations per instance.
- `sm03_1`: 50 jobs, 20 machines, 250 operations.

## Integrated mechanism design

For each source instance:

1. Jobs are split into T1/T2 by operation-count order.
2. Within each service type, jobs are sorted by workload:
   `sum(min processing time for each operation)`.
3. The top 70% workload jobs in each service type are assigned to VC1; the rest
   are assigned to VC2. This creates VC1 load pressure while keeping VC2 non-empty.
4. SRUs are fixed:
   - U1,U5 = VC1-T1
   - U2,U6 = VC1-T2
   - U3,U7 = VC2-T1
   - U4,U8 = VC2-T2
5. Each job has two intra-chain same-type SRUs and two cross-chain same-type SRUs.
6. Processing options are equal across candidate SRUs:
   - adjusted processing time equals the source processing time.
   - unit processing cost depends only on base machine and is identical across SRUs.
7. Cross-chain use has moderate collaboration cost:
   - cross fixed cost = 90.0
   - cross transport time = 4 + job_id % 2
   - cross transport unit cost = 3.5

## Intended interpretation

These are mechanism instances, not replacements for the balanced formal benchmark.
They test whether cross-chain scheduling can release overloaded VC1 SRUs without
introducing artificial cross-chain processing-time advantages. The eight-SRU
extension also prevents cross-off from degenerating to a single feasible SRU per
job.

## Files

- `manifest.csv`: one row per generated instance.
- `*_integrated_mechanism.json`: generated MVC-SM-DFJSP instances.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build LAMED 2VC/2type/8SRU integrated mechanism MVC instances.")
    parser.add_argument("--input-dir", default="data/lamed")
    parser.add_argument("--output-dir", default="data/mvc_lamed_2vc2type8sru")
    parser.add_argument("--instances", nargs="+", default=["la31", "la32", "la33", "la34", "la35", "sm03_1"])
    parser.add_argument("--vc1-load-ratio", type=float, default=VC1_LOAD_RATIO)
    args = parser.parse_args()

    input_dir = _resolve(args.input_dir)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    for instance_id in args.instances:
        source_path = input_dir / f"{instance_id}.txt"
        if not source_path.exists():
            raise FileNotFoundError(f"Missing source instance: {source_path}")
        payload = build_payload(source_path, ratio=args.vc1_load_ratio)
        _assert_sanity(payload)
        out_path = output_dir / f"{payload['instance_name']}.json"
        _write_payload(payload, out_path)
        vc_counts = {str(vc["id"]): len(vc.get("jobs", [])) for vc in payload["value_chains"]}
        intra_total, cross_total = _candidate_sanity(payload)
        rows.append(
            {
                "instance": payload["instance_name"],
                "source_instance": payload["source_instance"],
                "source_file": source_path.as_posix(),
                "scenario": "integrated_mechanism",
                "ratio_policy": f"{args.vc1_load_ratio:.2f}",
                "cross_fixed_cost": 90.0,
                "cross_transport_time_base": 4,
                "cross_transport_time_jitter": 2,
                "cross_transport_unit_cost": 3.5,
                "jobs": payload["n_jobs"],
                "ops": sum(int(job["n_operations"]) for job in payload["jobs"]),
                "base_machines": payload["n_base_machines"],
                "value_chains": payload["n_value_chains"],
                "types": payload["n_types"],
                "srus": payload["n_srus"],
                "vc1_jobs": vc_counts.get("VC1", 0),
                "vc2_jobs": vc_counts.get("VC2", 0),
                "candidate_intra_total": intra_total,
                "candidate_cross_total": cross_total,
                "type_summary_json": json.dumps(payload["type_value_chain_summary"], ensure_ascii=False, sort_keys=True),
                "file": out_path.as_posix(),
            }
        )

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "instance",
            "source_instance",
            "source_file",
            "scenario",
            "ratio_policy",
            "cross_fixed_cost",
            "cross_transport_time_base",
            "cross_transport_time_jitter",
            "cross_transport_unit_cost",
            "jobs",
            "ops",
            "base_machines",
            "value_chains",
            "types",
            "srus",
            "vc1_jobs",
            "vc2_jobs",
            "candidate_intra_total",
            "candidate_cross_total",
            "type_summary_json",
            "file",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    _write_readme(output_dir)
    print(f"built_instances: {len(rows)}")
    print(f"output_dir: {output_dir.as_posix()}")
    print(f"manifest: {manifest_path.as_posix()}")


if __name__ == "__main__":
    main()
