from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run the expanded MVC-EDA-TS ablation package described in Section 2.6 "
            "of the manuscript completion checklist."
        )
    )
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-dir", default="reports/mvc_mk01_15_formal_80pop_150iter/ablation_expanded")
    parser.add_argument("--instances", default="mk01,mk05,mk10,mk13,mk15")
    parser.add_argument("--seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--popsize", type=int, default=80)
    parser.add_argument("--max-iter", type=int, default=150)
    parser.add_argument("--time-limit", type=float, default=12000.0)
    parser.add_argument("--cross-chain", choices=["off", "on"], default="on")
    parser.add_argument("--variant-set", choices=["official", "extended"], default="official")
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.add_argument(
        "--all-instances",
        action="store_true",
        help="Run MVC-MK01 through MVC-MK15 instead of the recommended five representative instances.",
    )
    args = parser.parse_args()

    instance_arg = "" if args.all_instances else args.instances
    cmd = [
        sys.executable,
        "scripts/run_mvc_full_ablation.py",
        "--input-dir",
        args.input_dir,
        "--out-dir",
        args.out_dir,
        "--instances",
        instance_arg,
        "--variant-set",
        args.variant_set,
        "--seeds",
        args.seeds,
        "--popsize",
        str(args.popsize),
        "--max-iter",
        str(args.max_iter),
        "--time-limit",
        str(args.time_limit),
        "--objective-dim",
        str(args.objective_dim),
        "--cross-chain",
        args.cross_chain,
    ]
    if args.resume:
        cmd.append("--resume")

    print("Expanded ablation command:")
    print(" ".join(cmd))
    subprocess.run(cmd, cwd=ROOT, check=True)


if __name__ == "__main__":
    main()
