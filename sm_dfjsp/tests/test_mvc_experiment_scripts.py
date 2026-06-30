from __future__ import annotations

import csv
import subprocess
import shutil
import sys
from pathlib import Path


def _local_tmp(root: Path, name: str) -> Path:
    out_dir = root / ".tmp_test_outputs" / name
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    return out_dir


def test_validate_mvc_instances_script_smoke():
    root = Path(__file__).resolve().parents[1]
    out_dir = _local_tmp(root, "script_validation")
    cmd = [
        sys.executable,
        "-B",
        "scripts/validate_mvc_instances.py",
        "--input-dir",
        "data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty",
        "--out-dir",
        str(out_dir),
        "--max-instances",
        "1",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "validated: 1/1" in completed.stdout
    assert (out_dir / "validation_summary.csv").exists()
    shutil.rmtree(out_dir)


def test_run_mvc_experiments_script_smoke():
    root = Path(__file__).resolve().parents[1]
    out_dir = _local_tmp(root, "mvc_experiments")
    cmd = [
        sys.executable,
        "-B",
        "scripts/run_mvc_experiments.py",
        "--out-dir",
        str(out_dir),
        "--max-instances",
        "1",
        "--popsize",
        "4",
        "--max-iter",
        "1",
        "--time-limit",
        "5",
        "--seeds",
        "20260428",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "out_dir:" in completed.stdout
    assert (out_dir / "metrics" / "metrics_summary.csv").exists()
    assert (out_dir / "pareto" / "all_pareto_points.csv").exists()
    assert list((out_dir / "pareto" / "combined_front_plots").glob("*_merged_on_off_nondominated_front.png"))
    assert (out_dir / "pareto" / "combined_front_plots" / "merged_on_off_nondominated_front_summary.csv").exists()
    assert list((out_dir / "pareto" / "algorithm_front_plots" / "by_instance").glob("*_algorithm_pareto_fronts.png"))
    assert (out_dir / "pareto" / "algorithm_front_plots" / "algorithm_pareto_front_summary.csv").exists()
    with (out_dir / "raw" / "runtime_summary.csv").open("r", newline="", encoding="utf-8") as f:
        runtime_rows = list(csv.DictReader(f))
    assert runtime_rows
    assert runtime_rows[0]["stop_reason"] in {"max_iter", "time_limit", "completed_without_iteration"}
    assert int(runtime_rows[0]["iterations_completed"]) >= 0
    shutil.rmtree(out_dir)


def test_run_mvc_ablation_script_smoke():
    root = Path(__file__).resolve().parents[1]
    out_dir = _local_tmp(root, "mvc_ablation")
    cmd = [
        sys.executable,
        "-B",
        "scripts/run_mvc_ablation.py",
        "--out-dir",
        str(out_dir),
        "--popsize",
        "4",
        "--max-iter",
        "1",
        "--time-limit",
        "5",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "done A0_full" in completed.stdout
    assert "done A5_no_archive" in completed.stdout
    assert (out_dir / "ablation_summary.csv").exists()
    shutil.rmtree(out_dir)


def test_run_mvc_sensitivity_script_smoke():
    root = Path(__file__).resolve().parents[1]
    out_dir = _local_tmp(root, "mvc_sensitivity")
    cmd = [
        sys.executable,
        "-B",
        "scripts/run_mvc_sensitivity.py",
        "--out-dir",
        str(out_dir),
        "--fixed-costs",
        "0",
        "--transport-cost-scales",
        "1.0,1.2",
        "--cross-time-scales",
        "0.8",
        "--cross-modes",
        "off,on",
        "--popsize",
        "4",
        "--max-iter",
        "1",
        "--time-limit",
        "5",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "ts=1.2" in completed.stdout
    assert "xt=0.8" in completed.stdout
    assert (out_dir / "sensitivity_summary.csv").exists()
    assert (out_dir / "sensitivity_selected.csv").exists()
    shutil.rmtree(out_dir)


def test_run_mvc_full_ablation_script_smoke():
    root = Path(__file__).resolve().parents[1]
    out_dir = _local_tmp(root, "mvc_full_ablation")
    cmd = [
        sys.executable,
        "-B",
        "scripts/run_mvc_full_ablation.py",
        "--out-dir",
        str(out_dir),
        "--max-instances",
        "1",
        "--seeds",
        "20260428",
        "--popsize",
        "4",
        "--max-iter",
        "1",
        "--time-limit",
        "5",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "full ablation" in completed.stdout
    assert (out_dir / "all_instance_ablation_summary.csv").exists()
    assert (out_dir / "by_instance" / "mk01" / "seed20260428" / "ablation_summary.csv").exists()
    shutil.rmtree(out_dir)


def test_run_mvc_full_sensitivity_script_smoke():
    root = Path(__file__).resolve().parents[1]
    out_dir = _local_tmp(root, "mvc_full_sensitivity")
    cmd = [
        sys.executable,
        "-B",
        "scripts/run_mvc_full_sensitivity.py",
        "--out-dir",
        str(out_dir),
        "--max-instances",
        "1",
        "--seeds",
        "20260428",
        "--fixed-costs",
        "0",
        "--transport-cost-scales",
        "1.0",
        "--cross-time-scales",
        "1.0",
        "--cross-modes",
        "off,on",
        "--popsize",
        "4",
        "--max-iter",
        "1",
        "--time-limit",
        "5",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "full sensitivity" in completed.stdout
    assert (out_dir / "all_instance_sensitivity_summary.csv").exists()
    assert (out_dir / "by_instance" / "mk01" / "seed20260428" / "sensitivity_summary.csv").exists()
    shutil.rmtree(out_dir)


def test_build_mvc_tables_and_figures_smoke():
    root = Path(__file__).resolve().parents[1]
    exp_dir = _local_tmp(root, "paper_exp")
    abl_dir = _local_tmp(root, "paper_abl")
    sen_dir = _local_tmp(root, "paper_sen")
    table_dir = _local_tmp(root, "paper_tables")
    figure_dir = _local_tmp(root, "paper_figures")
    subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/run_mvc_experiments.py",
            "--out-dir",
            str(exp_dir),
            "--max-instances",
            "1",
            "--popsize",
            "4",
            "--max-iter",
            "1",
            "--time-limit",
            "5",
            "--seeds",
            "20260428",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/run_mvc_ablation.py",
            "--out-dir",
            str(abl_dir),
            "--popsize",
            "4",
            "--max-iter",
            "1",
            "--time-limit",
            "5",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/run_mvc_sensitivity.py",
            "--out-dir",
            str(sen_dir),
            "--fixed-costs",
            "0",
            "--transport-cost-scales",
            "1.0",
            "--cross-time-scales",
            "1.0",
            "--popsize",
            "4",
            "--max-iter",
            "1",
            "--time-limit",
            "5",
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/build_mvc_tables.py",
            "--experiment-dir",
            str(exp_dir),
            "--ablation-dir",
            str(abl_dir),
            "--sensitivity-dir",
            str(sen_dir),
            "--out-dir",
            str(table_dir),
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-B",
            "scripts/build_mvc_figures.py",
            "--experiment-dir",
            str(exp_dir),
            "--ablation-dir",
            str(abl_dir),
            "--sensitivity-dir",
            str(sen_dir),
            "--out-dir",
            str(figure_dir),
        ],
        cwd=root,
        text=True,
        capture_output=True,
        check=True,
    )
    assert (table_dir / "table_symbol_definition.csv").exists()
    assert (table_dir / "table_algorithm_parameters.csv").exists()
    assert (table_dir / "table_explanatory_case.csv").exists()
    assert (table_dir / "table_figure_inventory.csv").exists()
    assert (table_dir / "table_neighborhood_contribution.csv").exists()
    assert (table_dir / "table_stop_reasons.csv").exists()
    assert (figure_dir / "problem_structure.png").exists()
    assert (figure_dir / "mvc_edats_flow.png").exists()
    assert (figure_dir / "explanatory_small_case.png").exists()
    assert list((figure_dir / "per_instance_nd" / "figures" / "on_off_nd").glob("*_on_off_all_seed_nd.png"))
    assert list((figure_dir / "algorithm_pareto_by_instance" / "by_instance").glob("*_algorithm_pareto_fronts.png"))
    shutil.rmtree(exp_dir)
    shutil.rmtree(abl_dir)
    shutil.rmtree(sen_dir)
    shutil.rmtree(table_dir)
    shutil.rmtree(figure_dir)


def test_run_mvc_formal_pipeline_smoke():
    root = Path(__file__).resolve().parents[1]
    out_root = _local_tmp(root, "formal_pipeline")
    cmd = [
        sys.executable,
        "-B",
        "scripts/run_mvc_formal_pipeline.py",
        "--out-root",
        str(out_root),
        "--max-instances",
        "1",
        "--main-seeds",
        "20260428",
        "--main-popsize",
        "4",
        "--main-max-iter",
        "1",
        "--main-time-limit",
        "5",
        "--ablation-instances",
        "mk05",
        "--ablation-seeds",
        "20260428",
        "--ablation-popsize",
        "4",
        "--ablation-max-iter",
        "1",
        "--ablation-time-limit",
        "5",
        "--sensitivity-instances",
        "mk05",
        "--sensitivity-seeds",
        "20260428",
        "--sensitivity-popsize",
        "4",
        "--sensitivity-max-iter",
        "1",
        "--sensitivity-time-limit",
        "5",
        "--fixed-costs",
        "0",
        "--transport-cost-scales",
        "1.0",
        "--cross-time-scales",
        "1.0",
    ]
    completed = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=True)
    assert "formal pipeline" in completed.stdout
    assert (out_root / "main_experiment" / "pareto" / "algorithm_front_plots" / "algorithm_pareto_front_summary.csv").exists()
    assert (out_root / "ablation_light" / "all_instance_ablation_summary.csv").exists()
    assert (out_root / "sensitivity_light" / "all_instance_sensitivity_summary.csv").exists()
    assert (out_root / "tables" / "table_figure_inventory.csv").exists()
    assert (out_root / "figures" / "algorithm_pareto_by_instance" / "algorithm_pareto_front_summary.csv").exists()
    shutil.rmtree(out_root)
