from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Sequence

from mvc_experiment_utils import ProgressBar


ROOT = Path(__file__).resolve().parents[1]


def _resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def _outputs_ready(paths: Sequence[str | Path]) -> bool:
    return all(_resolve(path).exists() and _resolve(path).stat().st_size >= 0 for path in paths)


def _run_step(
    name: str,
    cmd: list[str],
    outputs: Sequence[str | Path],
    resume: bool,
    status_path: Path,
    progress: ProgressBar,
) -> None:
    if resume and _outputs_ready(outputs):
        print(f"[skip] {name}: expected outputs already exist", flush=True)
        _write_status(status_path, name, "skipped", cmd)
        progress.update(status=f"skip {name}")
        print("", flush=True)
        return
    print(f"[run] {name}", flush=True)
    print(" ".join(cmd), flush=True)
    started = time.time()
    subprocess.run(cmd, cwd=ROOT, check=True)
    _write_status(status_path, name, "completed", cmd, elapsed_s=time.time() - started)
    progress.update(status=f"done {name}")
    print("", flush=True)


def _write_status(status_path: Path, step: str, state: str, cmd: Sequence[str], elapsed_s: float | None = None) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    if status_path.exists() and status_path.stat().st_size > 0:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    else:
        payload = {"steps": []}
    payload["steps"].append(
        {
            "step": step,
            "state": state,
            "command": list(cmd),
            "elapsed_s": elapsed_s,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the resumable MVC-SM-DFJSP pilot experiment pipeline.")
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--max-instances", type=int, default=15)
    parser.add_argument("--popsize", type=int, default=30)
    parser.add_argument("--max-iter", type=int, default=50)
    parser.add_argument("--time-limit", type=float, default=300.0)
    parser.add_argument("--seeds", default="20260428,20260429,20260430")
    parser.add_argument("--fixed-costs", default="0,10,20,40")
    parser.add_argument("--transport-cost-scales", default="0.8,1.0,1.2")
    parser.add_argument("--cross-time-scales", default="0.8,1.0,1.2")
    parser.add_argument("--experiment-dir", default="reports/mvc_mk01_15_formal_2obj/main_experiment")
    parser.add_argument("--ablation-dir", default="reports/mvc_mk01_15_formal_2obj/ablation")
    parser.add_argument("--sensitivity-dir", default="reports/mvc_mk01_15_formal_2obj/sensitivity")
    parser.add_argument("--tables-dir", default="reports/mvc_mk01_15_formal_2obj/tables")
    parser.add_argument("--figures-dir", default="reports/mvc_mk01_15_formal_2obj/figures")
    parser.add_argument("--validation-dir", default="reports/mvc_mk01_15_formal_2obj/validation")
    parser.add_argument("--status-file", default="reports/mvc_mk01_15_formal_2obj/pipeline_status.json")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    args = parser.parse_args()

    py = sys.executable
    status_path = _resolve(args.status_file)
    resume_flag = ["--resume"] if args.resume else []

    steps = [
        (
            "validate instances",
            [
                py,
                "scripts/validate_mvc_instances.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                args.validation_dir,
                "--max-instances",
                str(args.max_instances),
            ],
            [Path(args.validation_dir) / "validation_summary.csv"],
        ),
        (
            "main comparison",
            [
                py,
                "scripts/run_mvc_experiments.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                args.experiment_dir,
                "--max-instances",
                str(args.max_instances),
                "--popsize",
                str(args.popsize),
                "--max-iter",
                str(args.max_iter),
                "--time-limit",
                str(args.time_limit),
                "--seeds",
                args.seeds,
                *resume_flag,
            ],
            [
                Path(args.experiment_dir) / "metrics" / "metrics_summary.csv",
                Path(args.experiment_dir) / "raw" / "runtime_summary.csv",
                Path(args.experiment_dir) / "pareto" / "all_pareto_points.csv",
            ],
        ),
        (
            "ablation",
            [
                py,
                "scripts/run_mvc_full_ablation.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                args.ablation_dir,
                "--max-instances",
                str(args.max_instances),
                "--popsize",
                str(args.popsize),
                "--max-iter",
                str(args.max_iter),
                "--time-limit",
                str(args.time_limit),
                "--seeds",
                args.seeds,
                *resume_flag,
            ],
            [
                Path(args.ablation_dir) / "all_instance_ablation_summary.csv",
                Path(args.ablation_dir) / "all_instance_ablation_history.csv",
            ],
        ),
        (
            "sensitivity",
            [
                py,
                "scripts/run_mvc_full_sensitivity.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                args.sensitivity_dir,
                "--max-instances",
                str(args.max_instances),
                "--fixed-costs",
                args.fixed_costs,
                "--transport-cost-scales",
                args.transport_cost_scales,
                "--cross-time-scales",
                args.cross_time_scales,
                "--popsize",
                str(args.popsize),
                "--max-iter",
                str(args.max_iter),
                "--time-limit",
                str(args.time_limit),
                "--seeds",
                args.seeds,
                *resume_flag,
            ],
            [
                Path(args.sensitivity_dir) / "all_instance_sensitivity_summary.csv",
                Path(args.sensitivity_dir) / "all_instance_sensitivity_selected.csv",
            ],
        ),
        (
            "tables",
            [
                py,
                "scripts/build_mvc_tables.py",
                "--experiment-dir",
                args.experiment_dir,
                "--ablation-dir",
                args.ablation_dir,
                "--sensitivity-dir",
                args.sensitivity_dir,
                "--out-dir",
                args.tables_dir,
            ],
            [
                Path(args.tables_dir) / "table_algorithm_performance.csv",
                Path(args.tables_dir) / "table_stop_reasons.csv",
                Path(args.tables_dir) / "statistical_tests.csv",
            ],
        ),
        (
            "figures",
            [
                py,
                "scripts/build_mvc_figures.py",
                "--experiment-dir",
                args.experiment_dir,
                "--ablation-dir",
                args.ablation_dir,
                "--sensitivity-dir",
                args.sensitivity_dir,
                "--out-dir",
                args.figures_dir,
            ],
            [
                Path(args.figures_dir) / "pareto_fronts.png",
                Path(args.figures_dir) / "problem_structure.png",
                Path(args.figures_dir) / "mvc_edats_flow.png",
            ],
        ),
    ]

    progress = ProgressBar(len(steps), "pipeline")
    for name, cmd, outputs in steps:
        _run_step(name, cmd, outputs, args.resume, status_path, progress)
    progress.finish()
    print(f"pipeline_status: {status_path.as_posix()}")
    print(f"tables_dir: {_resolve(args.tables_dir).as_posix()}")
    print(f"figures_dir: {_resolve(args.figures_dir).as_posix()}")


if __name__ == "__main__":
    main()
