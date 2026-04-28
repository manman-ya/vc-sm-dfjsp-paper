from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd: list[str], cwd: Path) -> None:
    print(">>", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["quick", "full"], default="quick")
    parser.add_argument("--skip-taguchi", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    py = sys.executable

    run_cmd([py, "scripts/build_sdmk.py"], root)
    run_cmd([py, "scripts/validate_sdmk_dataset.py", "--out-dir", "reports/repro/validation"], root)

    if args.mode == "quick":
        run_cmd(
            [
                py,
                "scripts/run_experiments_repeated.py",
                "--config",
                "configs/repro/experiment_01_15_quick.yaml",
                "--out-dir",
                "reports/repro/compare_01_15_quick",
            ],
            root,
        )
        run_cmd(
            [
                py,
                "scripts/run_ablation_repeated.py",
                "--config",
                "configs/repro/ablation_01_15_quick.yaml",
                "--out-dir",
                "reports/repro/ablation_01_15_quick",
            ],
            root,
        )
        if not args.skip_taguchi:
            run_cmd(
                [
                    py,
                    "scripts/tune_params_taguchi.py",
                    "--instance",
                    "sdmk15",
                    "--runs-per-combo",
                    "2",
                    "--time-limit",
                    "8",
                    "--max-iter",
                    "3",
                    "--out-dir",
                    "reports/repro/taguchi_01_15_quick",
                ],
                root,
            )
    else:
        run_cmd(
            [
                py,
                "scripts/run_experiments_repeated.py",
                "--config",
                "configs/repro/experiment_01_15.yaml",
                "--out-dir",
                "reports/repro/compare_01_15",
            ],
            root,
        )
        run_cmd(
            [
                py,
                "scripts/run_ablation_repeated.py",
                "--config",
                "configs/repro/ablation_01_15.yaml",
                "--out-dir",
                "reports/repro/ablation_01_15",
            ],
            root,
        )
        if not args.skip_taguchi:
            run_cmd(
                [
                    py,
                    "scripts/tune_params_taguchi.py",
                    "--instance",
                    "sdmk15",
                    "--runs-per-combo",
                    "30",
                    "--time-limit",
                    "100",
                    "--max-iter",
                    "100",
                    "--out-dir",
                    "reports/repro/taguchi_01_15",
                ],
                root,
            )

    print("done: repro_mk01_15")


if __name__ == "__main__":
    main()

