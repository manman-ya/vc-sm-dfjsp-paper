from __future__ import annotations

import argparse
import csv
import copy
import json
import math
import sys
from pathlib import Path
from typing import Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.data.mvc_io import load_mvc_instance_json, validate_mvc_instance


DEFAULT_INPUT_DIR = "data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty"
DEFAULT_INSTANCES = ["mk14", "mk15"]
SRU_BY_TYPE_AND_VC = {
    ("T1", "VC1"): "U1",
    ("T2", "VC1"): "U2",
    ("T1", "VC2"): "U3",
    ("T2", "VC2"): "U4",
}


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _job_key(job_id: int) -> str:
    return f"J{job_id}"


def _job_workload(job: dict) -> float:
    workload = 0.0
    for op in job["operations"]:
        option_times = [
            float(item["adjusted_processing_time"])
            for options in op["processing_options_by_sru"].values()
            for item in options
        ]
        workload += min(option_times)
    return workload


def _sru_value_chain(payload: dict) -> Dict[str, str]:
    return {str(sru["id"]): str(sru["value_chain"]) for sru in payload["srus"]}


def _same_type_srus(payload: dict, type_label: str) -> List[str]:
    candidates = payload.get("candidate_srus_by_type", {}).get(type_label)
    if candidates:
        return [str(x) for x in candidates]
    return [str(sru["id"]) for sru in payload["srus"] if str(sru["type"]) == type_label]


def _candidate_split(payload: dict, type_label: str, job_vc: str) -> tuple[List[str], List[str], List[str]]:
    sru_vc = _sru_value_chain(payload)
    same_type = _same_type_srus(payload, type_label)
    intra = [sid for sid in same_type if sru_vc[sid] == job_vc]
    cross = [sid for sid in same_type if sru_vc[sid] != job_vc]
    return intra + cross, intra, cross


def _ordered_processing_options(op: dict, candidate_srus: Iterable[str]) -> dict:
    by_sru = op["processing_options_by_sru"]
    ordered = {sid: by_sru[sid] for sid in candidate_srus if sid in by_sru}
    for sid, options in by_sru.items():
        if sid not in ordered:
            ordered[sid] = options
    return ordered


def _update_assignment_metadata(payload: dict) -> None:
    value_chain_jobs: Dict[str, List[int]] = {str(vc["id"]): [] for vc in payload["value_chains"]}
    compatibility: Dict[str, dict] = {}

    for job in payload["jobs"]:
        jid = int(job["job_id"])
        job_vc = str(job["value_chain"])
        job_type = str(job["type"])
        candidates, intra, cross = _candidate_split(payload, job_type, job_vc)
        job["candidate_srus"] = candidates
        value_chain_jobs.setdefault(job_vc, []).append(jid)
        compatibility[_job_key(jid)] = {
            "candidate_srus": candidates,
            "intra_chain_srus": intra,
            "cross_chain_srus": cross,
        }
        for op in job["operations"]:
            op["processing_options_by_sru"] = _ordered_processing_options(op, candidates)

    for vc in payload["value_chains"]:
        vc["jobs"] = sorted(value_chain_jobs.get(str(vc["id"]), []))
    payload["job_sru_compatibility"] = compatibility


def _rebuild_transport_and_cross_chain(
    payload: dict,
    *,
    cross_fixed_cost: float,
    cross_transport_time_base: int,
    cross_transport_time_jitter: int,
    cross_transport_unit_cost: float,
) -> None:
    sru_vc = _sru_value_chain(payload)
    transport_time: Dict[str, Dict[str, int]] = {}
    transport_cost: Dict[str, Dict[str, float]] = {}
    cross_chain: Dict[str, Dict[str, dict]] = {}

    for job in payload["jobs"]:
        jid = int(job["job_id"])
        jkey = _job_key(jid)
        job_vc = str(job["value_chain"])
        transport_time[jkey] = {}
        transport_cost[jkey] = {}
        cross_chain[jkey] = {}
        for sid in job["candidate_srus"]:
            is_cross = job_vc != sru_vc[sid]
            if is_cross:
                jitter = jid % max(cross_transport_time_jitter, 1)
                t = int(cross_transport_time_base + jitter)
                fixed = float(cross_fixed_cost)
                unit_cost = float(cross_transport_unit_cost)
            else:
                t = int(2 + jid % 2)
                fixed = 0.0
                unit_cost = 1.8

            transport_time[jkey][sid] = t
            transport_cost[jkey][sid] = float(round(t * unit_cost, 6))
            cross_chain[jkey][sid] = {
                "job_value_chain": job_vc,
                "sru_value_chain": sru_vc[sid],
                "is_cross_chain": bool(is_cross),
                "cross_chain_fixed_cost": float(round(fixed, 6)),
                "cross_chain_cost_rate": 0.0,
                "estimated_cross_chain_cost": float(round(fixed, 6)),
            }

    payload["transport_time"] = transport_time
    payload["transport_cost"] = transport_cost
    payload["cross_chain"] = cross_chain


def _assign_intra_congested_value_chains(payload: dict, ratio: float) -> None:
    jobs_by_type: Dict[str, List[dict]] = {}
    for job in payload["jobs"]:
        jobs_by_type.setdefault(str(job["type"]), []).append(job)

    for jobs in jobs_by_type.values():
        ordered = sorted(jobs, key=lambda item: (-_job_workload(item), int(item["job_id"])))
        vc1_count = min(len(ordered) - 1, max(1, int(math.ceil(len(ordered) * ratio))))
        for pos, job in enumerate(ordered):
            job["value_chain"] = "VC1" if pos < vc1_count else "VC2"


def _apply_cross_time_advantage(payload: dict, scale: float) -> None:
    sru_vc = _sru_value_chain(payload)
    for job in payload["jobs"]:
        job_vc = str(job["value_chain"])
        for op in job["operations"]:
            for sid, options in op["processing_options_by_sru"].items():
                if job_vc == sru_vc[str(sid)]:
                    continue
                for option in options:
                    original = int(option["adjusted_processing_time"])
                    option.setdefault("original_adjusted_processing_time", original)
                    option["adjusted_processing_time"] = int(max(1, round(original * scale)))
                    option["mechanism_processing_time_scale"] = float(scale)


def _mark_common_metadata(payload: dict, *, scenario: str, source_name: str) -> None:
    payload["source_instance"] = source_name
    payload["mechanism_scenario"] = scenario
    notes = payload.setdefault("notes", {})
    notes["mechanism_scenario"] = scenario
    notes["mechanism_source_instance_name"] = source_name
    notes["mechanism_generated_by"] = "scripts/build_mvc_mechanism_instances.py"
    notes["mechanism_status"] = "generated_for_3.1_cross_chain_mechanism_analysis"


def build_intra_congested(payload: dict, *, ratio: float, cross_fixed_cost: float) -> dict:
    out = copy.deepcopy(payload)
    source_name = str(out["instance_name"])
    out["instance_name"] = f"{out['source_instance']}_mvc_2vc_2type_4sru_intra_congested"
    _assign_intra_congested_value_chains(out, ratio)
    _update_assignment_metadata(out)
    _rebuild_transport_and_cross_chain(
        out,
        cross_fixed_cost=cross_fixed_cost,
        cross_transport_time_base=4,
        cross_transport_time_jitter=2,
        cross_transport_unit_cost=3.2,
    )
    _mark_common_metadata(out, scenario="intra_congested", source_name=source_name)
    out["notes"]["mechanism_design"] = (
        "Jobs are reassigned within each service type so that about "
        f"{ratio:.0%} of each type belongs to VC1. Processing times remain equal across SRUs; "
        "cross-chain fixed cost is moderate so that cross-on can release the overloaded intra-chain SRUs."
    )
    return out


def build_cross_time_advantage(payload: dict, *, scale: float, cross_fixed_cost: float) -> dict:
    out = copy.deepcopy(payload)
    source_name = str(out["instance_name"])
    out["instance_name"] = f"{out['source_instance']}_mvc_2vc_2type_4sru_cross_time_advantage"
    _update_assignment_metadata(out)
    _apply_cross_time_advantage(out, scale)
    _rebuild_transport_and_cross_chain(
        out,
        cross_fixed_cost=cross_fixed_cost,
        cross_transport_time_base=5,
        cross_transport_time_jitter=2,
        cross_transport_unit_cost=4.0,
    )
    _mark_common_metadata(out, scenario="cross_time_advantage", source_name=source_name)
    out["notes"]["mechanism_design"] = (
        "Intra-chain SRUs keep the original processing times, whereas cross-chain SRUs use "
        f"adjusted_processing_time = round(original * {scale:.2f}). Transport and fixed costs remain high enough "
        "to test whether the algorithm trades additional collaboration cost for shorter makespan."
    )
    return out


def _assert_mechanism_sanity(payload: dict) -> None:
    for job in payload["jobs"]:
        comp = payload["job_sru_compatibility"][_job_key(int(job["job_id"]))]
        if len(comp["intra_chain_srus"]) != 1 or len(comp["cross_chain_srus"]) != 1:
            raise AssertionError(f"Unexpected candidate split for J{job['job_id']}: {comp}")
        for sid in job["candidate_srus"]:
            if sid not in payload["transport_time"][_job_key(int(job["job_id"]))]:
                raise AssertionError(f"Missing transport_time for J{job['job_id']}-{sid}")
            if sid not in payload["cross_chain"][_job_key(int(job["job_id"]))]:
                raise AssertionError(f"Missing cross_chain metadata for J{job['job_id']}-{sid}")


def _source_file(input_dir: Path, instance: str) -> Path:
    matches = sorted(input_dir.glob(f"{instance}_mvc_2vc_2type_4sru_equalproc_vcpenalty.json"))
    if not matches:
        raise FileNotFoundError(f"Cannot find source JSON for {instance} in {input_dir}")
    return matches[0]


def _write_payload(payload: dict, path: Path) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    inst = load_mvc_instance_json(path)
    validate_mvc_instance(inst)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build 3.1 cross-chain mechanism instances for MVC-SM-DFJSP.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--instances", nargs="+", default=DEFAULT_INSTANCES)
    parser.add_argument("--intra-congestion-ratio", type=float, default=0.75)
    parser.add_argument("--intra-cross-fixed-cost", type=float, default=80.0)
    parser.add_argument("--cross-time-scale", type=float, default=0.75)
    parser.add_argument("--cross-time-fixed-cost", type=float, default=120.0)
    args = parser.parse_args()

    input_dir = _resolve(args.input_dir)
    output_dir = _resolve(args.output_dir) if args.output_dir else input_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    for instance in args.instances:
        source_path = _source_file(input_dir, instance)
        source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        variants = [
            build_intra_congested(
                source_payload,
                ratio=args.intra_congestion_ratio,
                cross_fixed_cost=args.intra_cross_fixed_cost,
            ),
            build_cross_time_advantage(
                source_payload,
                scale=args.cross_time_scale,
                cross_fixed_cost=args.cross_time_fixed_cost,
            ),
        ]
        for payload in variants:
            _assert_mechanism_sanity(payload)
            out_path = output_dir / f"{payload['instance_name']}.json"
            _write_payload(payload, out_path)
            vc_counts = {
                str(vc["id"]): len(vc.get("jobs", []))
                for vc in payload.get("value_chains", [])
            }
            rows.append(
                {
                    "instance": payload["instance_name"],
                    "source_file": source_path.as_posix(),
                    "scenario": payload["mechanism_scenario"],
                    "jobs": payload["n_jobs"],
                    "vc1_jobs": vc_counts.get("VC1", 0),
                    "vc2_jobs": vc_counts.get("VC2", 0),
                    "file": out_path.as_posix(),
                }
            )

    manifest_path = output_dir / "mechanism_manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["instance", "source_file", "scenario", "jobs", "vc1_jobs", "vc2_jobs", "file"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"built_mechanism_instances: {len(rows)}")
    print(f"manifest: {manifest_path.as_posix()}")


if __name__ == "__main__":
    main()
