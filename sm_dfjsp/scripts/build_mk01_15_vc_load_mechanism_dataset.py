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

from build_mvc_mechanism_instances import (  # noqa: E402
    _assert_mechanism_sanity,
    _job_key,
    _job_workload,
    build_cross_time_advantage,
    build_intra_congested,
)
from smdfjsp.data.mvc_io import load_mvc_instance_json, validate_mvc_instance  # noqa: E402


DEFAULT_INPUT_DIR = "data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty"
DEFAULT_OUTPUT_DIR = "data/mvc_mk01_15_2vc4sru_mechanism_vc_load"


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def _mk_index(instance_id: str) -> int:
    return int(instance_id.lower().replace("mk", ""))


def _ratio_for_instance(instance_id: str) -> float:
    idx = _mk_index(instance_id)
    if idx <= 5:
        return 0.70
    if idx <= 10:
        return 0.75
    return 0.80


def _source_file(input_dir: Path, instance_id: str) -> Path:
    matches = sorted(input_dir.glob(f"{instance_id}_mvc_2vc_2type_4sru_equalproc_vcpenalty.json"))
    if not matches:
        raise FileNotFoundError(f"Cannot find source JSON for {instance_id} in {input_dir}")
    return matches[0]


def _write_payload(payload: dict, path: Path) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    inst = load_mvc_instance_json(path)
    validate_mvc_instance(inst)


def _type_vc_summary(payload: dict) -> Dict[str, dict]:
    summary: Dict[str, dict] = {}
    for type_label in sorted({str(job["type"]) for job in payload["jobs"]}):
        rows = [job for job in payload["jobs"] if str(job["type"]) == type_label]
        total_workload = sum(_job_workload(job) for job in rows)
        type_summary: Dict[str, object] = {
            "jobs": len(rows),
            "total_workload": round(total_workload, 6),
        }
        for vc in ("VC1", "VC2"):
            vc_rows = [job for job in rows if str(job["value_chain"]) == vc]
            workload = sum(_job_workload(job) for job in vc_rows)
            type_summary[f"{vc}_jobs"] = len(vc_rows)
            type_summary[f"{vc}_workload"] = round(workload, 6)
            type_summary[f"{vc}_workload_share"] = round(workload / total_workload, 6) if total_workload else 0.0
        summary[type_label] = type_summary
    return summary


def _overall_vc_counts(payload: dict) -> Dict[str, int]:
    counts = {"VC1": 0, "VC2": 0}
    for vc in payload.get("value_chains", []):
        counts[str(vc["id"])] = len(vc.get("jobs", []))
    return counts


def _candidate_sanity(payload: dict) -> tuple[int, int]:
    intra_total = 0
    cross_total = 0
    for job in payload["jobs"]:
        comp = payload["job_sru_compatibility"][_job_key(int(job["job_id"]))]
        intra_total += len(comp["intra_chain_srus"])
        cross_total += len(comp["cross_chain_srus"])
    return intra_total, cross_total


def _row(payload: dict, source_path: Path, scenario: str, ratio: float | str, output_path: Path) -> dict:
    vc_counts = _overall_vc_counts(payload)
    type_summary = _type_vc_summary(payload)
    intra_total, cross_total = _candidate_sanity(payload)
    return {
        "instance": payload["instance_name"],
        "source_instance": payload["source_instance"],
        "source_file": source_path.as_posix(),
        "scenario": scenario,
        "ratio_policy": ratio,
        "jobs": payload["n_jobs"],
        "ops": sum(int(job["n_operations"]) for job in payload["jobs"]),
        "vc1_jobs": vc_counts.get("VC1", 0),
        "vc2_jobs": vc_counts.get("VC2", 0),
        "candidate_intra_total": intra_total,
        "candidate_cross_total": cross_total,
        "type_summary_json": json.dumps(type_summary, ensure_ascii=False, sort_keys=True),
        "file": output_path.as_posix(),
    }


def _write_readme(output_dir: Path, args: argparse.Namespace) -> None:
    text = f"""# MVC-MK01-15 2VC/2Type/4SRU Mechanism Dataset with Value-Chain Load Skew

This dataset is generated from `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`
without overwriting the original formal benchmark.

## Purpose

The formal equal-processing dataset assigns jobs almost evenly to VC1 and VC2.
That design is suitable for a fair baseline comparison, but it weakly activates
cross-chain scheduling because the intra-chain SRUs are not strongly congested.
This dataset adds mechanism-oriented instances that deliberately create
intra-chain load imbalance or cross-chain processing-time advantage.

## Common structure

- Value chains: VC1 and VC2.
- Service types: T1 and T2.
- SRUs: U1=VC1-T1, U2=VC1-T2, U3=VC2-T1, U4=VC2-T2.
- Each job keeps exactly one intra-chain SRU and one same-type cross-chain SRU.
- All jobs keep release_time = 0 and one-job-one-SRU hard assignment.

## Scenario 1: intra_congested

Within each service type, jobs are sorted by workload
`sum(min adjusted_processing_time for each operation)`.
The highest-workload jobs are assigned to VC1 and the remaining jobs to VC2:

- mk01-mk05: top 70% per type -> VC1.
- mk06-mk10: top 75% per type -> VC1.
- mk11-mk15: top 80% per type -> VC1.

This makes U1 and U2 the congested intra-chain SRUs, while U3 and U4 become
same-type cross-chain relief resources. Processing times remain equal across
candidate SRUs. Cross-chain transport and fixed cost are moderated:

- cross fixed cost = {args.intra_cross_fixed_cost}
- cross transport time = 4 + job_id % 2
- cross transport unit cost = 3.2

## Scenario 2: cross_time_advantage

The original balanced value-chain assignment is kept, but cross-chain processing
options are faster:

- cross adjusted_processing_time = round(original * {args.cross_time_scale})
- cross fixed cost = {args.cross_time_fixed_cost}
- cross transport time = 5 + job_id % 2
- cross transport unit cost = 4.0

This scenario tests whether the algorithm trades additional collaboration cost
for shorter makespan when cross-chain SRUs have a real time advantage.

## Files

- `manifest.csv`: one row per generated JSON instance.
- `README.md`: this design description.
- `*_intra_congested.json`: value-chain-load-skew mechanism instances.
- `*_cross_time_advantage.json`: cross-chain-time-advantage mechanism instances.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build MK01-15 MVC mechanism dataset with value-chain load skew.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--instances", nargs="+", default=[f"mk{i:02d}" for i in range(1, 16)])
    parser.add_argument("--intra-cross-fixed-cost", type=float, default=80.0)
    parser.add_argument("--cross-time-scale", type=float, default=0.75)
    parser.add_argument("--cross-time-fixed-cost", type=float, default=120.0)
    args = parser.parse_args()

    input_dir = _resolve(args.input_dir)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    for instance_id in args.instances:
        source_path = _source_file(input_dir, instance_id)
        source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        ratio = _ratio_for_instance(instance_id)

        intra_payload = build_intra_congested(
            source_payload,
            ratio=ratio,
            cross_fixed_cost=args.intra_cross_fixed_cost,
        )
        intra_payload["notes"]["value_chain_load_ratio_policy"] = (
            "mk01-mk05=0.70, mk06-mk10=0.75, mk11-mk15=0.80, applied independently within each service type."
        )
        _assert_mechanism_sanity(intra_payload)
        intra_path = output_dir / f"{intra_payload['instance_name']}.json"
        _write_payload(intra_payload, intra_path)
        rows.append(_row(intra_payload, source_path, "intra_congested", f"{ratio:.2f}", intra_path))

        time_payload = build_cross_time_advantage(
            source_payload,
            scale=args.cross_time_scale,
            cross_fixed_cost=args.cross_time_fixed_cost,
        )
        _assert_mechanism_sanity(time_payload)
        time_path = output_dir / f"{time_payload['instance_name']}.json"
        _write_payload(time_payload, time_path)
        rows.append(_row(time_payload, source_path, "cross_time_advantage", f"scale={args.cross_time_scale:.2f}", time_path))

    manifest_path = output_dir / "manifest.csv"
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "instance",
            "source_instance",
            "source_file",
            "scenario",
            "ratio_policy",
            "jobs",
            "ops",
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

    _write_readme(output_dir, args)
    print(f"built_instances: {len(rows)}")
    print(f"output_dir: {output_dir.as_posix()}")
    print(f"manifest: {manifest_path.as_posix()}")


if __name__ == "__main__":
    main()
