from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Sequence

from mvc_experiment_utils import ProgressBar, read_csv, summarize_metrics, write_csv


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
    return all(_resolve(path).exists() and _resolve(path).stat().st_size > 0 for path in paths) and _meta_matches(
        meta_path,
        expected_meta,
    )


def _write_status(status_path: Path, step: str, state: str, detail: Sequence[str] | str, elapsed_s: float | None = None) -> None:
    status_path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() and status_path.stat().st_size > 0 else {"steps": []}
    payload["steps"].append(
        {
            "step": step,
            "state": state,
            "detail": list(detail) if not isinstance(detail, str) else detail,
            "elapsed_s": elapsed_s,
            "time": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
    )
    status_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_command(
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
    _write_status(status_path, name, "completed", cmd, time.time() - started)
    progress.update(status=f"done {name}")
    print("", flush=True)


def _run_callable(
    name: str,
    action: Callable[[], None],
    outputs: Sequence[str | Path],
    resume: bool,
    status_path: Path,
    progress: ProgressBar,
) -> None:
    if resume and _outputs_ready(outputs):
        print(f"[skip] {name}: expected outputs already exist", flush=True)
        _write_status(status_path, name, "skipped", name)
        progress.update(status=f"skip {name}")
        print("", flush=True)
        return
    print(f"[run] {name}", flush=True)
    started = time.time()
    action()
    _write_status(status_path, name, "completed", name, time.time() - started)
    progress.update(status=f"done {name}")
    print("", flush=True)


def _prepare_inputs(source_input_dir: Path, prepared_input_dir: Path, resume: bool, expected_instances: int) -> None:
    prepared_input_dir.mkdir(parents=True, exist_ok=True)
    sources = sorted(
        p
        for p in source_input_dir.glob("mk??_mvc_*.json")
        if "before_conflict_enhancement" not in p.name and not p.name.endswith(".bak.json")
    )
    if expected_instances > 0 and len(sources) != expected_instances:
        raise RuntimeError(f"Expected {expected_instances} MVC instances, found {len(sources)} in {source_input_dir}")

    rows = []
    for source in sources:
        target = prepared_input_dir / source.name
        if not resume or not target.exists() or source.stat().st_mtime > target.stat().st_mtime:
            shutil.copy2(source, target)
        rows.append(
            {
                "instance_file": target.as_posix(),
                "source_file": source.as_posix(),
                "bytes": target.stat().st_size,
            }
        )

    manifest = prepared_input_dir / "input_manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["instance_file", "source_file", "bytes"])
        writer.writeheader()
        writer.writerows(rows)


def _combine_experiment_1_2(exp1_dir: Path, exp2_dir: Path, combined_dir: Path, args: argparse.Namespace) -> None:
    pareto_rows = []
    runtime_rows = []
    selected_rows = []
    seen = set()
    for source_name, source_dir in [("experiment1_algorithm_off", exp1_dir), ("experiment2_mvc_on", exp2_dir)]:
        for row in read_csv(source_dir / "pareto" / "all_pareto_points.csv"):
            key = (
                row.get("instance"),
                row.get("algorithm"),
                row.get("cross_chain"),
                row.get("seed"),
                row.get("solution_id"),
                row.get("total_cost"),
                row.get("makespan"),
            )
            if key in seen:
                continue
            seen.add(key)
            item = dict(row)
            item["result_source"] = source_name
            pareto_rows.append(item)
        for row in read_csv(source_dir / "raw" / "runtime_summary.csv"):
            item = dict(row)
            item["result_source"] = source_name
            runtime_rows.append(item)
        for row in read_csv(source_dir / "raw" / "selected_compromise.csv"):
            item = dict(row)
            item["result_source"] = source_name
            selected_rows.append(item)

    write_csv(combined_dir / "pareto" / "all_pareto_points.csv", pareto_rows)
    write_csv(combined_dir / "metrics" / "metrics_summary.csv", summarize_metrics(pareto_rows, int(args.objective_dim)))
    write_csv(combined_dir / "raw" / "runtime_summary.csv", runtime_rows)
    write_csv(combined_dir / "raw" / "selected_compromise.csv", selected_rows)
    (combined_dir / "run_meta.json").parent.mkdir(parents=True, exist_ok=True)
    (combined_dir / "run_meta.json").write_text(
        json.dumps(
            {
                "source": "run_mvc_experiment_1_2_formal.py",
                "experiment1_dir": exp1_dir.as_posix(),
                "experiment2_dir": exp2_dir.as_posix(),
                "seeds": args.seeds,
                "popsize": args.popsize,
                "max_iter": args.max_iter,
                "time_limit": args.time_limit,
                "objective_dim": args.objective_dim,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run MVC Experiment 1-2 only, with progress and resumable outputs.")
    parser.add_argument("--source-input-dir", default="data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty")
    parser.add_argument("--out-root", default="reports/mvc_experiment_1_2_formal_80pop_150iter")
    parser.add_argument("--prepared-input-name", default="mk01_15_mvc_instances")
    parser.add_argument("--expected-instances", type=int, default=15, help="Set to 0 to disable the input count check.")
    parser.add_argument("--seeds", default="20260428,20260429,20260430,20260431,20260432,20260433,20260434,20260435,20260436,20260437,20260438,20260439,20260440,20260441,20260442,20260443,20260444,20260445,20260446,20260447")
    parser.add_argument("--popsize", type=int, default=80)
    parser.add_argument("--max-iter", type=int, default=150)
    parser.add_argument("--time-limit", type=float, default=12000.0)
    parser.add_argument("--objective-dim", type=int, choices=[2], default=2)
    parser.add_argument("--max-instances", type=int, default=None, help="Optional cap for smoke tests; omit for the formal run.")
    parser.add_argument("--resume", dest="resume", action="store_true", default=True)
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    args = parser.parse_args()

    py = sys.executable
    out_root = _resolve(args.out_root)
    source_input_dir = _resolve(args.source_input_dir)
    prepared_input_dir = out_root / "inputs" / args.prepared_input_name
    exp1_dir = out_root / "experiment1_algorithm_off"
    exp2_dir = out_root / "experiment2_mvc_on"
    combined_dir = out_root / "combined_experiment_1_2"
    unified_dir = out_root / "combined_experiment_1_2_unified_metrics"
    stat_dir = out_root / "stat_tests"
    tables_dir = out_root / "tables"
    figures_dir = out_root / "figures"
    validation_dir = out_root / "validation"
    empty_plain_dir = out_root / "empty_plain"
    empty_ablation_dir = out_root / "empty_ablation"
    empty_sensitivity_dir = out_root / "empty_sensitivity"
    status_path = out_root / "experiment_1_2_pipeline_status.json"

    for directory in (empty_plain_dir, empty_ablation_dir, empty_sensitivity_dir):
        directory.mkdir(parents=True, exist_ok=True)

    resume_flag = ["--resume"] if args.resume else []
    max_instances_args = ["--max-instances", str(args.max_instances)] if args.max_instances is not None else []
    input_dir_arg = prepared_input_dir.as_posix()

    exp1_meta = {
        "input_dir": input_dir_arg,
        "out_dir": exp1_dir.as_posix(),
        "algorithms": "nsgaii,moead,edats-baseline,mvc-edats",
        "cross_modes": "off",
        "seeds": args.seeds,
        "popsize": args.popsize,
        "max_iter": args.max_iter,
        "time_limit": args.time_limit,
        "objective_dim": args.objective_dim,
        "max_instances": args.max_instances,
    }
    exp2_meta = {
        "input_dir": input_dir_arg,
        "out_dir": exp2_dir.as_posix(),
        "algorithms": "mvc-edats",
        "cross_modes": "off,on",
        "seeds": args.seeds,
        "popsize": args.popsize,
        "max_iter": args.max_iter,
        "time_limit": args.time_limit,
        "objective_dim": args.objective_dim,
        "max_instances": args.max_instances,
    }

    steps_total = 10
    progress = ProgressBar(steps_total, "experiment 1-2 pipeline")

    _run_callable(
        "prepare formal inputs",
        lambda: _prepare_inputs(source_input_dir, prepared_input_dir, args.resume, args.expected_instances),
        [prepared_input_dir / "input_manifest.csv"],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "validate formal inputs",
        [
            py,
            "scripts/validate_mvc_instances.py",
            "--input-dir",
            input_dir_arg,
            "--out-dir",
            validation_dir.as_posix(),
        ],
        [validation_dir / "validation_summary.csv"],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "experiment 1 algorithm comparison off",
        [
            py,
            "scripts/run_mvc_experiments.py",
            "--input-dir",
            input_dir_arg,
            "--out-dir",
            exp1_dir.as_posix(),
            "--algorithms",
            "nsgaii,moead,edats-baseline,mvc-edats",
            "--cross-modes",
            "off",
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
            *max_instances_args,
            *resume_flag,
        ],
        [
            exp1_dir / "metrics" / "metrics_summary.csv",
            exp1_dir / "pareto" / "all_pareto_points.csv",
            exp1_dir / "raw" / "runtime_summary.csv",
        ],
        args.resume,
        status_path,
        progress,
        exp1_dir / "run_meta.json",
        exp1_meta,
    )

    _run_command(
        "experiment 2 mvc-edats off/on",
        [
            py,
            "scripts/run_mvc_experiments.py",
            "--input-dir",
            input_dir_arg,
            "--out-dir",
            exp2_dir.as_posix(),
            "--algorithms",
            "mvc-edats",
            "--cross-modes",
            "off,on",
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
            *max_instances_args,
            *resume_flag,
        ],
        [
            exp2_dir / "metrics" / "metrics_summary.csv",
            exp2_dir / "pareto" / "all_pareto_points.csv",
            exp2_dir / "raw" / "runtime_summary.csv",
        ],
        args.resume,
        status_path,
        progress,
        exp2_dir / "run_meta.json",
        exp2_meta,
    )

    _run_callable(
        "combine experiment 1-2",
        lambda: _combine_experiment_1_2(exp1_dir, exp2_dir, combined_dir, args),
        [
            combined_dir / "pareto" / "all_pareto_points.csv",
            combined_dir / "metrics" / "metrics_summary.csv",
            combined_dir / "raw" / "runtime_summary.csv",
        ],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "combined on-off fronts",
        [py, "scripts/build_mvc_instance_nd_fronts.py", "--experiment-dir", combined_dir.as_posix()],
        [combined_dir / "pareto" / "combined_front_plots" / "merged_on_off_nondominated_front_summary.csv"],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "combined algorithm fronts",
        [py, "scripts/build_mvc_algorithm_fronts.py", "--experiment-dir", combined_dir.as_posix()],
        [combined_dir / "pareto" / "algorithm_front_plots" / "algorithm_pareto_front_summary.csv"],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "statistical tests",
        [
            py,
            "scripts/build_mvc_stat_tests.py",
            "--main-dir",
            combined_dir.as_posix(),
            "--plain-dir",
            empty_plain_dir.as_posix(),
            "--combined-dir",
            unified_dir.as_posix(),
            "--out-dir",
            stat_dir.as_posix(),
            "--alpha",
            "0.05",
        ],
        [
            stat_dir / "wilcoxon_hv_igd.csv",
            stat_dir / "wilcoxon_cost_makespan.csv",
            stat_dir / "friedman_ranking.csv",
            stat_dir / "stat_tests_summary.md",
        ],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "tables and figures",
        [
            py,
            "scripts/build_mvc_tables.py",
            "--experiment-dir",
            combined_dir.as_posix(),
            "--ablation-dir",
            empty_ablation_dir.as_posix(),
            "--sensitivity-dir",
            empty_sensitivity_dir.as_posix(),
            "--out-dir",
            tables_dir.as_posix(),
        ],
        [
            tables_dir / "table_algorithm_performance.csv",
            tables_dir / "table_cross_chain_analysis.csv",
            tables_dir / "table_cost_breakdown.csv",
        ],
        args.resume,
        status_path,
        progress,
    )

    _run_command(
        "summary figures",
        [
            py,
            "scripts/build_mvc_figures.py",
            "--experiment-dir",
            combined_dir.as_posix(),
            "--ablation-dir",
            empty_ablation_dir.as_posix(),
            "--sensitivity-dir",
            empty_sensitivity_dir.as_posix(),
            "--out-dir",
            figures_dir.as_posix(),
        ],
        [figures_dir / "pareto_fronts.png", figures_dir / "main_hv.png"],
        args.resume,
        status_path,
        progress,
    )

    progress.finish()
    print(f"out_root: {out_root.as_posix()}")
    print(f"status: {status_path.as_posix()}")
    print(f"experiment1: {exp1_dir.as_posix()}")
    print(f"experiment2: {exp2_dir.as_posix()}")
    print(f"combined: {combined_dir.as_posix()}")
    print(f"stat_tests: {stat_dir.as_posix()}")
    print(f"tables: {tables_dir.as_posix()}")
    print(f"figures: {figures_dir.as_posix()}")


if __name__ == "__main__":
    main()
