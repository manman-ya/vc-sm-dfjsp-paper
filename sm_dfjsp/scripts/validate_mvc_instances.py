from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.data.mvc_io import get_candidate_srus, load_mvc_instance_json, validate_mvc_instance

from mvc_experiment_utils import load_instances, write_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate MVC-SM-DFJSP JSON instances.")
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-dir", default="reports/mvc_validation/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--max-instances", type=int, default=None)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    rows = []
    for path in load_instances(args.input_dir, args.max_instances):
        row = {"file": path.as_posix(), "instance": path.stem, "valid": False, "message": ""}
        try:
            inst = load_mvc_instance_json(path)
            validate_mvc_instance(inst)
            cross_ok = all(len(get_candidate_srus(job, inst, True)) >= len(get_candidate_srus(job, inst, False)) for job in inst.jobs)
            fixed_cost_ok = True
            cost_rate_ok = True
            for job in inst.jobs:
                for sid in get_candidate_srus(job, inst, True):
                    key = (job.job_id, sid)
                    is_cross = bool(inst.is_cross_chain.get(key, False))
                    fixed = float(inst.cross_chain_fixed_cost.get(key, 0.0))
                    rate = float(inst.cross_chain_cost_rate.get(key, 0.0))
                    fixed_cost_ok = fixed_cost_ok and (is_cross or abs(fixed) <= 1e-12)
                    cost_rate_ok = cost_rate_ok and abs(rate) <= 1e-12
            row.update(
                {
                    "instance": inst.name,
                    "jobs": inst.num_jobs,
                    "srus": inst.num_srus,
                    "types": inst.num_types,
                    "objective_definition": "total_cost=processing_cost+transport_cost+cross_fixed_cost; makespan=max(C_j+transport_time)",
                    "cross_candidate_check": cross_ok,
                    "fixed_cross_cost_check": fixed_cost_ok,
                    "cost_rate_zero_check": cost_rate_ok,
                    "valid": True,
                }
            )
            if not fixed_cost_ok or not cost_rate_ok:
                row["valid"] = False
                row["message"] = "Invalid formal fixed-cost cost model metadata"
        except Exception as exc:  # noqa: BLE001 - validation summary should keep going.
            row["message"] = str(exc)
        rows.append(row)
    write_csv(out_dir / "validation_summary.csv", rows)
    passed = sum(1 for r in rows if r["valid"])
    print(f"validated: {passed}/{len(rows)}")
    print(f"summary: {(out_dir / 'validation_summary.csv').as_posix()}")
    if passed != len(rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
