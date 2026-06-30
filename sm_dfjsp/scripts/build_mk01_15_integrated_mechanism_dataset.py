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

from build_mk01_15_vc_load_mechanism_dataset import (  # noqa: E402
    _candidate_sanity,
    _ratio_for_instance,
    _source_file,
    _type_vc_summary,
    _write_payload,
)
from build_mvc_mechanism_instances import (  # noqa: E402
    _assert_mechanism_sanity,
    _mark_common_metadata,
    _rebuild_transport_and_cross_chain,
    _update_assignment_metadata,
    build_intra_congested,
)


DEFAULT_INPUT_DIR = "data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty"
DEFAULT_OUTPUT_DIR = "data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc"


def _resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def build_integrated_mechanism(
    payload: dict,
    *,
    ratio: float,
    cross_fixed_cost: float,
    cross_transport_time_base: int,
    cross_transport_time_jitter: int,
    cross_transport_unit_cost: float,
) -> dict:
    out = build_intra_congested(payload, ratio=ratio, cross_fixed_cost=cross_fixed_cost)
    source_name = str(payload["instance_name"])
    out["instance_name"] = f"{payload['source_instance']}_mvc_2vc_2type_4sru_integrated_mechanism"
    _update_assignment_metadata(out)
    _rebuild_transport_and_cross_chain(
        out,
        cross_fixed_cost=cross_fixed_cost,
        cross_transport_time_base=cross_transport_time_base,
        cross_transport_time_jitter=cross_transport_time_jitter,
        cross_transport_unit_cost=cross_transport_unit_cost,
    )
    _mark_common_metadata(out, scenario="integrated_mechanism", source_name=source_name)
    notes = out.setdefault("notes", {})
    notes["mechanism_design"] = (
        "Integrated mechanism instance: high-workload jobs within each service type are assigned to VC1 "
        f"with ratio={ratio:.2f}, creating U1/U2 intra-chain congestion. Cross-chain SRUs keep the same "
        "processing time and unit processing cost for each operation-base-machine pair, but use moderate "
        "transport and fixed collaboration costs. The instance is designed to test whether cross-chain "
        "scheduling can release overloaded intra-chain SRUs without adding an artificial processing-time advantage."
    )
    notes["value_chain_load_ratio_policy"] = (
        "mk01-mk05=0.70, mk06-mk10=0.75, mk11-mk15=0.80, applied independently within each service type."
    )
    notes["processing_time_consistency_rule"] = (
        "For every job, operation, and base_machine_id, adjusted_processing_time is identical across all candidate SRUs."
    )
    notes["processing_cost_consistency_rule"] = (
        "For every job, operation, and base_machine_id, unit_processing_cost is identical across all candidate SRUs."
    )
    notes["cross_fixed_cost"] = float(cross_fixed_cost)
    notes["cross_transport_time"] = f"{cross_transport_time_base} + job_id % {cross_transport_time_jitter}"
    notes["cross_transport_unit_cost"] = float(cross_transport_unit_cost)
    return out


def _assert_equal_operation_machine_options(payload: dict) -> None:
    for job in payload["jobs"]:
        job_id = int(job["job_id"])
        for op in job["operations"]:
            op_id = int(op["op_id"])
            by_machine: Dict[int, List[dict]] = {}
            for sid, options in op["processing_options_by_sru"].items():
                for option in options:
                    base_machine_id = int(option["base_machine_id"])
                    by_machine.setdefault(base_machine_id, []).append(
                        {
                            "sru": str(sid),
                            "adjusted_processing_time": int(option["adjusted_processing_time"]),
                            "unit_processing_cost": float(option["unit_processing_cost"]),
                        }
                    )
            for base_machine_id, options in by_machine.items():
                times = {item["adjusted_processing_time"] for item in options}
                costs = {item["unit_processing_cost"] for item in options}
                if len(times) != 1 or len(costs) != 1:
                    raise AssertionError(
                        "Inconsistent operation-machine option for "
                        f"J{job_id}-O{op_id}-M{base_machine_id}: {options}"
                    )


def _vc_counts(payload: dict) -> Dict[str, int]:
    return {str(vc["id"]): len(vc.get("jobs", [])) for vc in payload.get("value_chains", [])}


def _write_readme(output_dir: Path, args: argparse.Namespace) -> None:
    text = f"""# MVC-MK01-15 2VC/2Type/4SRU Integrated Mechanism Dataset

This dataset is generated from `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`
without overwriting the original formal benchmark or the separated mechanism dataset.

## Why this dataset has only 15 instances

The separated mechanism dataset contains two independent scenario families:
`intra_congested` and `cross_time_advantage`. This integrated dataset keeps the
intra-chain congestion construction only, and uses cross-chain candidates with
explicit transport and fixed collaboration costs. It can be used as a single
15-instance mechanism benchmark without changing processing times across SRUs.

## Integrated design

For each source instance mk01-mk15:

1. Within each service type, jobs are sorted by workload
   `sum(min adjusted_processing_time for each operation)`.
2. The highest-workload jobs are assigned to VC1:
   - mk01-mk05: top 70% per type -> VC1.
   - mk06-mk10: top 75% per type -> VC1.
   - mk11-mk15: top 80% per type -> VC1.
3. SRUs remain fixed:
   - U1=VC1-T1
   - U2=VC1-T2
   - U3=VC2-T1
   - U4=VC2-T2
4. Each job keeps exactly one intra-chain SRU and one same-type cross-chain SRU.
5. Processing options are consistent across SRUs:
   - for the same job, operation, and base machine, adjusted processing time is identical across candidate SRUs.
   - for the same job, operation, and base machine, unit processing cost is identical across candidate SRUs.
6. Cross-chain use has moderate collaboration cost:
   - cross fixed cost = {args.cross_fixed_cost}
   - cross transport time = {args.cross_transport_time_base} + job_id % {args.cross_transport_time_jitter}
   - cross transport unit cost = {args.cross_transport_unit_cost}

## Intended interpretation

These instances are not replacements for the fair equal-processing benchmark.
They are mechanism instances designed to make cross-chain scheduling observable:
VC1 owns most high-workload jobs, so U1 and U2 become congested; VC2's same-type
SRUs, U3 and U4, provide load relief when cross-chain is enabled. Any benefit
comes from congestion relief, parallel capacity, and load balancing rather than
from cross-chain processing-time reduction.

## Files

- `manifest.csv`: one row per generated JSON instance.
- `*_integrated_mechanism.json`: one integrated mechanism instance per mk source instance.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a 15-instance integrated MVC mechanism dataset.")
    parser.add_argument("--input-dir", default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--instances", nargs="+", default=[f"mk{i:02d}" for i in range(1, 16)])
    parser.add_argument("--cross-fixed-cost", type=float, default=90.0)
    parser.add_argument("--cross-transport-time-base", type=int, default=4)
    parser.add_argument("--cross-transport-time-jitter", type=int, default=2)
    parser.add_argument("--cross-transport-unit-cost", type=float, default=3.5)
    args = parser.parse_args()

    input_dir = _resolve(args.input_dir)
    output_dir = _resolve(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    rows: List[dict] = []
    for instance_id in args.instances:
        source_path = _source_file(input_dir, instance_id)
        source_payload = json.loads(source_path.read_text(encoding="utf-8"))
        ratio = _ratio_for_instance(instance_id)
        payload = build_integrated_mechanism(
            source_payload,
            ratio=ratio,
            cross_fixed_cost=args.cross_fixed_cost,
            cross_transport_time_base=args.cross_transport_time_base,
            cross_transport_time_jitter=args.cross_transport_time_jitter,
            cross_transport_unit_cost=args.cross_transport_unit_cost,
        )
        _assert_mechanism_sanity(payload)
        _assert_equal_operation_machine_options(payload)
        out_path = output_dir / f"{payload['instance_name']}.json"
        _write_payload(payload, out_path)
        vc_counts = _vc_counts(payload)
        intra_total, cross_total = _candidate_sanity(payload)
        rows.append(
            {
                "instance": payload["instance_name"],
                "source_instance": payload["source_instance"],
                "source_file": source_path.as_posix(),
                "scenario": "integrated_mechanism",
                "ratio_policy": f"{ratio:.2f}",
                "cross_fixed_cost": args.cross_fixed_cost,
                "cross_transport_time_base": args.cross_transport_time_base,
                "cross_transport_time_jitter": args.cross_transport_time_jitter,
                "cross_transport_unit_cost": args.cross_transport_unit_cost,
                "jobs": payload["n_jobs"],
                "ops": sum(int(job["n_operations"]) for job in payload["jobs"]),
                "vc1_jobs": vc_counts.get("VC1", 0),
                "vc2_jobs": vc_counts.get("VC2", 0),
                "candidate_intra_total": intra_total,
                "candidate_cross_total": cross_total,
                "type_summary_json": json.dumps(_type_vc_summary(payload), ensure_ascii=False, sort_keys=True),
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
