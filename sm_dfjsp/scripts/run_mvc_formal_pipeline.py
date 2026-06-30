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


def _meta_matches(meta_path: str | Path | None, expected: dict[str, object] | None) -> bool:
    if not meta_path or not expected:
        return True
    path = _resolve(meta_path)
    if not path.exists() or path.stat().st_size == 0:
        return False
    actual = json.loads(path.read_text(encoding="utf-8"))
    for key, value in expected.items():
        if str(actual.get(key)) != str(value):
            return False
    return True


def _outputs_ready(
    paths: Sequence[str | Path],
    meta_path: str | Path | None = None,
    expected_meta: dict[str, object] | None = None,
) -> bool:
    return all(_resolve(path).exists() and _resolve(path).stat().st_size >= 0 for path in paths) and _meta_matches(meta_path, expected_meta)


def _write_status(status_path: Path, step: str, state: str, cmd: Sequence[str], elapsed_s: float | None = None) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() and status_path.stat().st_size > 0 else {"steps": []}
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


def _run_step(
    name: str,
    cmd: list[str],
    outputs: Sequence[str | Path],
    resume: bool,
    status_path: Path,
    progress: ProgressBar,
    meta_path: str | Path | None = None,
    expected_meta: dict[str, object] | None = None,
) -> None:
    if resume and _outputs_ready(outputs, meta_path, expected_meta):
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the formal MVC-MK01-15 experiment pipeline with resumable progress.")
    parser.add_argument("--input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-root", default="reports/mvc_mk01_15_formal_80pop_150iter")
    parser.add_argument("--max-instances", type=int, default=None, help="Optional cap for smoke tests; default runs all instances.")
    parser.add_argument("--main-seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--main-popsize", type=int, default=80)
    parser.add_argument("--main-max-iter", type=int, default=150)
    parser.add_argument("--main-time-limit", type=float, default=12000.0)
    parser.add_argument("--ablation-instances", default="mk05,mk10,mk15")
    parser.add_argument("--ablation-seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--ablation-popsize", type=int, default=80)
    parser.add_argument("--ablation-max-iter", type=int, default=150)
    parser.add_argument("--ablation-time-limit", type=float, default=12000.0)
    parser.add_argument("--sensitivity-instances", default="mk05,mk10,mk15")
    parser.add_argument("--sensitivity-seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--sensitivity-popsize", type=int, default=50)
    parser.add_argument("--sensitivity-max-iter", type=int, default=100)
    parser.add_argument("--sensitivity-time-limit", type=float, default=6000.0)
    parser.add_argument("--fixed-costs", default="0,10,20,40")
    parser.add_argument("--transport-cost-scales", default="0.8,1.0,1.2")
    parser.add_argument("--cross-time-scales", default="0.8,1.0,1.2")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    args = parser.parse_args()

    py = sys.executable
    out_root = Path(args.out_root)
    experiment_dir = out_root / "main_experiment"
    ablation_dir = out_root / "ablation_light"
    sensitivity_dir = out_root / "sensitivity_light"
    tables_dir = out_root / "tables"
    figures_dir = out_root / "figures"
    status_path = _resolve(out_root / "formal_pipeline_status.json")
    resume_flag = ["--resume"] if args.resume else []

    steps = [
        (
            "main comparison",
            [
                py,
                "scripts/run_mvc_experiments.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                str(experiment_dir),
                "--algorithms",
                "nsgaii,moead,mvc-edats",
                "--cross-modes",
                "off,on",
                "--seeds",
                args.main_seeds,
                "--popsize",
                str(args.main_popsize),
                "--max-iter",
                str(args.main_max_iter),
                "--time-limit",
                str(args.main_time_limit),
                "--objective-dim",
                "2",
                *(["--max-instances", str(args.max_instances)] if args.max_instances is not None else []),
                *resume_flag,
            ],
            [
                experiment_dir / "metrics" / "metrics_summary.csv",
                experiment_dir / "pareto" / "all_pareto_points.csv",
                experiment_dir / "pareto" / "combined_front_plots" / "merged_on_off_nondominated_front_summary.csv",
                experiment_dir / "pareto" / "algorithm_front_plots" / "algorithm_pareto_front_summary.csv",
            ],
            experiment_dir / "run_meta.json",
            {
                "input_dir": args.input_dir,
                "out_dir": str(experiment_dir),
                "algorithms": "nsgaii,moead,mvc-edats",
                "cross_modes": "off,on",
                "seeds": args.main_seeds,
                "popsize": args.main_popsize,
                "max_iter": args.main_max_iter,
                "time_limit": args.main_time_limit,
                "objective_dim": 2,
            },
        ),
        (
            "light ablation",
            [
                py,
                "scripts/run_mvc_full_ablation.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                str(ablation_dir),
                "--instances",
                args.ablation_instances,
                "--variant-set",
                "official",
                "--seeds",
                args.ablation_seeds,
                "--popsize",
                str(args.ablation_popsize),
                "--max-iter",
                str(args.ablation_max_iter),
                "--time-limit",
                str(args.ablation_time_limit),
                "--objective-dim",
                "2",
                "--cross-chain",
                "on",
                *(["--max-instances", str(args.max_instances)] if args.max_instances is not None else []),
                *resume_flag,
            ],
            [
                ablation_dir / "all_instance_ablation_summary.csv",
                ablation_dir / "all_instance_ablation_history.csv",
            ],
            ablation_dir / "run_meta.json",
            {
                "input_dir": args.input_dir,
                "out_dir": str(ablation_dir),
                "variant_set": "official",
                "seeds": args.ablation_seeds,
                "popsize": args.ablation_popsize,
                "max_iter": args.ablation_max_iter,
                "time_limit": args.ablation_time_limit,
                "objective_dim": 2,
                "cross_chain": "on",
                "instances": args.ablation_instances,
            },
        ),
        (
            "light sensitivity",
            [
                py,
                "scripts/run_mvc_full_sensitivity.py",
                "--input-dir",
                args.input_dir,
                "--out-dir",
                str(sensitivity_dir),
                "--instances",
                args.sensitivity_instances,
                "--fixed-costs",
                args.fixed_costs,
                "--transport-cost-scales",
                args.transport_cost_scales,
                "--cross-time-scales",
                args.cross_time_scales,
                "--cross-modes",
                "off,on",
                "--seeds",
                args.sensitivity_seeds,
                "--popsize",
                str(args.sensitivity_popsize),
                "--max-iter",
                str(args.sensitivity_max_iter),
                "--time-limit",
                str(args.sensitivity_time_limit),
                "--objective-dim",
                "2",
                *(["--max-instances", str(args.max_instances)] if args.max_instances is not None else []),
                *resume_flag,
            ],
            [
                sensitivity_dir / "all_instance_sensitivity_summary.csv",
                sensitivity_dir / "all_instance_sensitivity_selected.csv",
            ],
            sensitivity_dir / "run_meta.json",
            {
                "input_dir": args.input_dir,
                "out_dir": str(sensitivity_dir),
                "fixed_costs": args.fixed_costs,
                "transport_cost_scales": args.transport_cost_scales,
                "cross_time_scales": args.cross_time_scales,
                "cross_modes": "off,on",
                "seeds": args.sensitivity_seeds,
                "popsize": args.sensitivity_popsize,
                "max_iter": args.sensitivity_max_iter,
                "time_limit": args.sensitivity_time_limit,
                "objective_dim": 2,
                "instances": args.sensitivity_instances,
            },
        ),
        (
            "tables",
            [
                py,
                "scripts/build_mvc_tables.py",
                "--experiment-dir",
                str(experiment_dir),
                "--ablation-dir",
                str(ablation_dir),
                "--sensitivity-dir",
                str(sensitivity_dir),
                "--out-dir",
                str(tables_dir),
            ],
            [
                tables_dir / "table_algorithm_performance.csv",
                tables_dir / "table_figure_inventory.csv",
                tables_dir / "statistical_tests.csv",
            ],
            None,
            None,
        ),
        (
            "figures",
            [
                py,
                "scripts/build_mvc_figures.py",
                "--experiment-dir",
                str(experiment_dir),
                "--ablation-dir",
                str(ablation_dir),
                "--sensitivity-dir",
                str(sensitivity_dir),
                "--out-dir",
                str(figures_dir),
            ],
            [
                figures_dir / "pareto_fronts.png",
                figures_dir / "per_instance_nd" / "merged_on_off_nondominated_front_summary.csv",
                figures_dir / "algorithm_pareto_by_instance" / "algorithm_pareto_front_summary.csv",
            ],
            None,
            None,
        ),
    ]

    progress = ProgressBar(len(steps), "formal pipeline")
    for name, cmd, outputs, meta_path, expected_meta in steps:
        _run_step(name, cmd, outputs, args.resume, status_path, progress, meta_path, expected_meta)
    progress.finish()
    print(f"pipeline_status: {status_path.as_posix()}")
    print(f"main_experiment: {_resolve(experiment_dir).as_posix()}")
    print(f"ablation_light: {_resolve(ablation_dir).as_posix()}")
    print(f"sensitivity_light: {_resolve(sensitivity_dir).as_posix()}")
    print(f"tables_dir: {_resolve(tables_dir).as_posix()}")
    print(f"figures_dir: {_resolve(figures_dir).as_posix()}")


if __name__ == "__main__":
    main()
