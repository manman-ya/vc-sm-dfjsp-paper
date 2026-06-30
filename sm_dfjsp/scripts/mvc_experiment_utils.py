from __future__ import annotations

import csv
import json
import math
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from smdfjsp.baselines.mvc_edats_baseline import run_mvc_edats_baseline
from smdfjsp.baselines.mvc_moead import MVCMOEADConfig, run_mvc_moead
from smdfjsp.baselines.mvc_nsgaii import MVCNSGAIIConfig, run_mvc_nsgaii
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.data.mvc_io import load_mvc_instance_json
from smdfjsp.metrics.multiobjective import (
    auto_reference_point,
    build_reference_front,
    gd,
    hypervolume,
    igd,
    normalized_hypervolume,
    objective_bounds,
    raw_igd,
    spacing,
)
from smdfjsp.model.mvc_evaluator import evaluate_mvc_individual
from smdfjsp.mvc_eda_ts import MVCEDATS, MVCEDATSConfig


class ProgressBar:
    def __init__(self, total: int, label: str, width: int = 32):
        self.total = max(1, int(total))
        self.label = label
        self.width = width
        self.done = 0
        self.start = time.time()
        self._last_len = 0

    def update(self, done: int | None = None, status: str = "") -> None:
        if done is None:
            self.done += 1
        else:
            self.done = int(done)
        self.done = max(0, min(self.done, self.total))
        ratio = self.done / self.total
        filled = int(round(self.width * ratio))
        bar = "#" * filled + "-" * (self.width - filled)
        elapsed = time.time() - self.start
        text = f"\r{self.label} [{bar}] {self.done}/{self.total} {ratio * 100:5.1f}% elapsed={elapsed:6.1f}s"
        if status:
            text += f" {status}"
        padding = max(0, self._last_len - len(text))
        sys.stdout.write(text + (" " * padding))
        sys.stdout.flush()
        self._last_len = len(text)

    def finish(self) -> None:
        self.update(self.total)
        sys.stdout.write("\n")
        sys.stdout.flush()


def resolve_path(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def parse_csv_list(value: str) -> List[str]:
    return [x.strip() for x in value.split(",") if x.strip()]


def parse_int_list(value: str) -> List[int]:
    return [int(x) for x in parse_csv_list(value)]


def write_csv(path: str | Path, rows: Sequence[Mapping[str, object]]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row.keys():
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: str | Path) -> List[dict]:
    path = Path(path)
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_instances(input_dir: str | Path, max_instances: int | None = None) -> List[Path]:
    input_dir = resolve_path(input_dir)
    files = sorted(
        p
        for p in input_dir.glob("*_mvc_*.json")
        if "before_conflict_enhancement" not in p.name and not p.name.endswith(".bak.json")
    )
    if max_instances is not None:
        files = files[: max(0, int(max_instances))]
    return files


def run_algorithm(
    instance: MVCSMDFJSPInstance,
    algorithm: str,
    mode: MVCModeConfig,
    seed: int,
    popsize: int,
    max_iter: int,
    time_limit: float,
    cfg_overrides: Mapping[str, object] | None = None,
    max_evaluations: int | None = None,
    time_measure: str = "wall",
):
    cfg_overrides = dict(cfg_overrides or {})
    start = time.time()
    if algorithm == "nsgaii":
        cfg = MVCNSGAIIConfig(
            popsize=popsize,
            max_iter=max_iter,
            time_limit_s=time_limit,
            max_evaluations=max_evaluations,
            time_measure=time_measure,
            seed=seed,
        )
        for key, value in cfg_overrides.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        result = run_mvc_nsgaii(instance, cfg, mode)
    elif algorithm == "moead":
        cfg = MVCMOEADConfig(
            popsize=popsize,
            max_iter=max_iter,
            time_limit_s=time_limit,
            max_evaluations=max_evaluations,
            time_measure=time_measure,
            seed=seed,
        )
        for key, value in cfg_overrides.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        result = run_mvc_moead(instance, cfg, mode)
    elif algorithm == "edats-baseline":
        cfg = MVCEDATSConfig(
            popsize=popsize,
            max_iter=max_iter,
            time_limit_s=time_limit,
            max_evaluations=max_evaluations,
            time_measure=time_measure,
            seed=seed,
            local_search_steps=int(cfg_overrides.pop("local_search_steps", 2)),
        )
        for key, value in cfg_overrides.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        result = run_mvc_edats_baseline(instance, cfg, mode)
    elif algorithm == "mvc-edats":
        cfg = MVCEDATSConfig(
            popsize=popsize,
            max_iter=max_iter,
            time_limit_s=time_limit,
            max_evaluations=max_evaluations,
            time_measure=time_measure,
            seed=seed,
        )
        for key, value in cfg_overrides.items():
            if hasattr(cfg, key):
                setattr(cfg, key, value)
        result = MVCEDATS(instance, cfg, mode).run()
    else:
        raise ValueError(f"unknown algorithm: {algorithm}")
    return result, time.time() - start


def stop_metadata(result, runtime_s: float) -> dict:
    iterations_completed = int(getattr(result, "iterations_completed", len(getattr(result, "history", []))))
    stop_reason = str(getattr(result, "stop_reason", "") or "")
    if not stop_reason:
        stop_reason = "max_iter" if iterations_completed > 0 else "completed_without_iteration"
    evaluations_completed = int(
        getattr(result, "evaluations_completed", getattr(result, "evaluation_count", 0))
    )
    phase_times = getattr(result, "phase_times", None) or getattr(result, "module_runtime_s", None) or {}
    metadata = {
        "stop_reason": stop_reason,
        "iterations_completed": iterations_completed,
        "algorithm_elapsed_s": float(getattr(result, "elapsed_s", runtime_s)),
        "budget_elapsed_s": float(getattr(result, "budget_elapsed_s", runtime_s)),
        "time_measure": str(getattr(result, "time_measure", "wall")),
        "evaluations_completed": evaluations_completed,
    }
    for phase, seconds in phase_times.items():
        metadata[f"module_{phase}_s"] = float(seconds)
    return metadata


def front_rows(
    instance: MVCSMDFJSPInstance,
    solutions: Sequence[EncodedIndividual],
    mode: MVCModeConfig,
    meta: Mapping[str, object],
) -> Tuple[List[dict], List[dict]]:
    rows: List[dict] = []
    detail_rows: List[dict] = []
    seen = set()
    for idx, sol in enumerate(solutions, start=1):
        ev = evaluate_mvc_individual(instance, sol, mode)
        if not ev.feasible:
            continue
        key = tuple(round(float(x), 8) for x in ev.objectives)
        if key in seen:
            continue
        seen.add(key)
        row = dict(meta)
        row.update(
            {
                "solution_id": idx,
                "total_cost": ev.total_cost,
                "makespan": ev.makespan,
                "max_sru_load": ev.max_sru_load,
                "cross_chain_jobs": ev.diagnostics.get("cross_chain_jobs", 0),
                "cross_chain_ratio": ev.diagnostics.get("cross_chain_ratio", 0.0),
                "sru_load_std": ev.diagnostics.get("sru_load_std", 0.0),
                "value_chain_load_std": ev.diagnostics.get("value_chain_load_std", 0.0),
                "cross_chain_flow": json.dumps(ev.diagnostics.get("cross_chain_flow", {}), ensure_ascii=False, sort_keys=True),
                "value_chain_inflow": json.dumps(ev.diagnostics.get("value_chain_inflow", {}), ensure_ascii=False, sort_keys=True),
                "value_chain_outflow": json.dumps(ev.diagnostics.get("value_chain_outflow", {}), ensure_ascii=False, sort_keys=True),
                "sru_loads": json.dumps(ev.sru_loads, ensure_ascii=False, sort_keys=True),
            }
        )
        row.update(ev.cost_breakdown)
        rows.append(row)
        detail_rows.append(
            {
                "solution_id": idx,
                "ua": json.dumps(sol.ua, ensure_ascii=False, sort_keys=True),
                "os": json.dumps(sol.os, ensure_ascii=False, sort_keys=True),
                "op": json.dumps({str(k): v for k, v in sol.op.items()}, ensure_ascii=False, sort_keys=True),
                "ms": json.dumps({str(k): v for k, v in sol.ms.items()}, ensure_ascii=False, sort_keys=True),
                "objectives": json.dumps(list(ev.objectives), ensure_ascii=False),
                "sru_loads": json.dumps(ev.sru_loads, ensure_ascii=False, sort_keys=True),
                "cross_chain_flow": json.dumps(ev.diagnostics.get("cross_chain_flow", {}), ensure_ascii=False, sort_keys=True),
            }
        )
    return rows, detail_rows


def select_compromise(rows: Sequence[Mapping[str, object]], objective_dim: int) -> Mapping[str, object] | None:
    if not rows:
        return None
    cols = ["total_cost", "makespan"]
    mins = {c: min(float(r[c]) for r in rows) for c in cols}
    maxs = {c: max(float(r[c]) for r in rows) for c in cols}

    def score(row: Mapping[str, object]) -> float:
        total = 0.0
        for col in cols:
            span = max(maxs[col] - mins[col], 1e-9)
            total += (float(row[col]) - mins[col]) / span
        return total

    return min(rows, key=score)


def objective_tuple(row: Mapping[str, object], objective_dim: int) -> Tuple[float, ...]:
    return (float(row["total_cost"]), float(row["makespan"]))


def summarize_metrics(rows: Sequence[Mapping[str, object]], objective_dim: int) -> List[dict]:
    optional_cols = ["variant_code", "variant", "fixed_cost", "transport_scale", "cross_time_scale", "cost_rate"]
    grouped: Dict[Tuple[str, ...], List[Mapping[str, object]]] = {}
    for row in rows:
        key_cols = ["instance", "algorithm", "cross_chain", "seed"] + [c for c in optional_cols if c in row]
        key = tuple(str(row.get(c, "")) for c in key_cols)
        grouped.setdefault(key, []).append(row)
    fronts = [[objective_tuple(r, objective_dim) for r in group] for group in grouped.values()]
    ref_front = build_reference_front(fronts)
    ref_point = auto_reference_point(fronts) if any(fronts) else (1.0, 1.0)
    lower_bounds, upper_bounds = objective_bounds(fronts) if any(fronts) else ((0.0, 0.0), (1.0, 1.0))

    instance_fronts: Dict[str, List[List[Tuple[float, ...]]]] = {}
    for key, group in grouped.items():
        instance_fronts.setdefault(key[0], []).append([objective_tuple(r, objective_dim) for r in group])
    instance_references: Dict[str, Tuple[List[Tuple[float, ...]], Tuple[float, ...], Tuple[float, ...]]] = {}
    for instance, compared_fronts in instance_fronts.items():
        instance_references[instance] = (
            build_reference_front(compared_fronts),
            *objective_bounds(compared_fronts),
        )
    out: List[dict] = []
    for key, group in sorted(grouped.items()):
        key_cols = ["instance", "algorithm", "cross_chain", "seed"] + [c for c in optional_cols if c in group[0]]
        front = [objective_tuple(r, objective_dim) for r in group]
        igd_reference, igd_lower_bounds, igd_upper_bounds = instance_references[key[0]]
        raw_hv = hypervolume(front, ref_point) if front else 0.0
        hv = normalized_hypervolume(front, ref_point, lower_bounds, upper_bounds) if front else 0.0
        row = {col: key[i] for i, col in enumerate(key_cols)}
        row.update(
            {
            "front_size": len(front),
            "hv": hv,
            "raw_hv": raw_hv,
            "gd": gd(front, ref_front),
            "igd": igd(front, igd_reference, igd_lower_bounds, igd_upper_bounds),
            "raw_igd": raw_igd(front, igd_reference),
            "spacing": spacing(front),
            "min_total_cost": min(float(r["total_cost"]) for r in group),
            "min_makespan": min(float(r["makespan"]) for r in group),
            "mean_total_cost": mean(float(r["total_cost"]) for r in group),
            "mean_makespan": mean(float(r["makespan"]) for r in group),
            "mean_cross_chain_ratio": mean(float(r.get("cross_chain_ratio", 0.0)) for r in group),
            "mean_cross_fixed_cost": mean(float(r.get("cross_fixed_cost", 0.0)) for r in group),
            "mean_transport_cost": mean(float(r.get("transport_cost", 0.0)) for r in group),
            "mean_sru_load_std": mean(float(r.get("sru_load_std", 0.0)) for r in group),
            "runtime_s": max(float(r.get("runtime_s", 0.0)) for r in group),
            "iterations_completed": max(int(float(r.get("iterations_completed", 0))) for r in group),
            "algorithm_elapsed_s": max(float(r.get("algorithm_elapsed_s", 0.0)) for r in group),
            "budget_elapsed_s": max(float(r.get("budget_elapsed_s", 0.0)) for r in group),
            "evaluations_completed": max(int(float(r.get("evaluations_completed", 0))) for r in group),
            "time_measure": str(group[0].get("time_measure", "wall")),
            "stop_reason": str(group[0].get("stop_reason", "")),
            }
        )
        module_cols = sorted({str(col) for r in group for col in r if str(col).startswith("module_") and str(col).endswith("_s")})
        for col in module_cols:
            values = [float(r[col]) for r in group if str(r.get(col, "")) not in {"", "nan"}]
            if values:
                row[col] = max(values)
        out.append(row)
    return out


def aggregate_mean(rows: Sequence[Mapping[str, object]], group_cols: Sequence[str], metric_cols: Sequence[str]) -> List[dict]:
    grouped: Dict[Tuple[str, ...], List[Mapping[str, object]]] = {}
    for row in rows:
        grouped.setdefault(tuple(str(row.get(c, "")) for c in group_cols), []).append(row)
    out: List[dict] = []
    for key, group in sorted(grouped.items()):
        item = {col: key[i] for i, col in enumerate(group_cols)}
        item["runs"] = len(group)
        for col in metric_cols:
            values = [float(r[col]) for r in group if str(r.get(col, "")) not in {"", "nan"} and math.isfinite(float(r[col]))]
            if values:
                item[f"mean_{col}"] = mean(values)
                item[f"best_{col}"] = max(values) if col == "hv" else min(values)
        out.append(item)
    return out
