from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping, Sequence

from build_mvc_instance_nd_fronts import _float, _non_dominated, _short_instance
from mvc_experiment_utils import ROOT, read_csv, write_csv


ALGORITHM_ORDER = ("nsgaii", "moead", "edats-baseline", "mvc-edats")
ALGORITHM_COLORS = {
    "nsgaii": "#4c78a8",
    "moead": "#f28e2b",
    "edats-baseline": "#7f3c8d",
    "mvc-edats": "#59a14f",
}
ALGORITHM_LABELS = {
    "nsgaii": "NSGA-II",
    "moead": "MOEA/D",
    "edats-baseline": "Plain EDA-TS",
    "mvc-edats": "MVC-EDA-TS",
}
MODE_MARKERS = {"off": "o", "on": "^"}


def _algorithm_order(rows: Sequence[dict]) -> list[str]:
    observed = {str(row.get("algorithm", "")).lower() for row in rows}
    ordered = [algorithm for algorithm in ALGORITHM_ORDER if algorithm in observed]
    ordered.extend(sorted(observed.difference(ordered)))
    return ordered


def _mode_order(rows: Sequence[dict]) -> list[str]:
    observed = {str(row.get("cross_chain", "")).lower() for row in rows}
    ordered = [mode for mode in ("off", "on") if mode in observed]
    ordered.extend(sorted(observed.difference(ordered)))
    return ordered


def _plot_algorithm_instance(rows: Sequence[dict], out_path: Path, title: str) -> None:
    if not rows:
        return
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8.0, 5.2), dpi=160)

    global_nd = _non_dominated(list(rows))
    if global_nd:
        ordered_global = sorted(global_nd, key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))
        ax.plot(
            [_float(r, "total_cost") for r in ordered_global],
            [_float(r, "makespan") for r in ordered_global],
            color="#9a9a9a",
            linewidth=1.2,
            alpha=0.55,
            label="global ND front",
            zorder=1,
        )

    summary_rows = []
    for algorithm in _algorithm_order(rows):
        for mode in _mode_order(rows):
            group = [
                r
                for r in rows
                if str(r.get("algorithm", "")).lower() == algorithm and str(r.get("cross_chain", "")).lower() == mode
            ]
            if not group:
                continue
            nd_rows = _non_dominated(group)
            ordered = sorted(nd_rows, key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))
            ax.plot(
                [_float(r, "total_cost") for r in ordered],
                [_float(r, "makespan") for r in ordered],
                color=ALGORITHM_COLORS.get(algorithm, "#666666"),
                linewidth=1.0,
                alpha=0.35,
                zorder=2,
            )
            ax.scatter(
                [_float(r, "total_cost") for r in ordered],
                [_float(r, "makespan") for r in ordered],
                s=28,
                color=ALGORITHM_COLORS.get(algorithm, "#666666"),
                marker=MODE_MARKERS.get(mode, "s"),
                label=f"{ALGORITHM_LABELS.get(algorithm, algorithm)}-{mode} (n={len(ordered)})",
                zorder=3,
            )
            summary_rows.append(
                {
                    "algorithm": algorithm,
                    "cross_chain": mode,
                    "input_points": len(group),
                    "nd_points": len(ordered),
                    "min_total_cost": min((_float(r, "total_cost") for r in ordered), default=""),
                    "min_makespan": min((_float(r, "makespan") for r in ordered), default=""),
                }
            )

    ax.set_xlabel("Total cost")
    ax.set_ylabel("Makespan")
    ax.set_title(title)
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
    write_csv(out_path.with_suffix(".summary.csv"), summary_rows)


def _plot_all_instances(instance_rows: Mapping[str, Sequence[dict]], out_path: Path) -> None:
    import math
    import matplotlib.pyplot as plt

    instances = sorted(instance_rows)
    if not instances:
        return
    cols = 3
    rows_n = math.ceil(len(instances) / cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(rows_n, cols, figsize=(cols * 5.2, rows_n * 3.6), dpi=160)
    axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]
    for ax, instance in zip(axes_list, instances):
        rows = list(instance_rows[instance])
        global_nd = _non_dominated(rows)
        if global_nd:
            ordered_global = sorted(global_nd, key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))
            ax.plot(
                [_float(r, "total_cost") for r in ordered_global],
                [_float(r, "makespan") for r in ordered_global],
                color="#9a9a9a",
                linewidth=0.9,
                alpha=0.5,
            )
        for algorithm in _algorithm_order(rows):
            for mode in _mode_order(rows):
                group = [
                    r
                    for r in rows
                    if str(r.get("algorithm", "")).lower() == algorithm and str(r.get("cross_chain", "")).lower() == mode
                ]
                if not group:
                    continue
                nd_rows = _non_dominated(group)
                ax.scatter(
                    [_float(r, "total_cost") for r in nd_rows],
                    [_float(r, "makespan") for r in nd_rows],
                    s=12,
                    color=ALGORITHM_COLORS.get(algorithm, "#666666"),
                    marker=MODE_MARKERS.get(mode, "s"),
                    label=f"{ALGORITHM_LABELS.get(algorithm, algorithm)}-{mode}",
                    alpha=0.85,
                )
        ax.set_title(_short_instance(instance), fontsize=10)
        ax.grid(alpha=0.22, linestyle="--")
        ax.tick_params(labelsize=8)
    for ax in axes_list[len(instances) :]:
        ax.axis("off")
    handles_by_label = {}
    for ax in axes_list[: len(instances)]:
        handles, labels = ax.get_legend_handles_labels()
        handles_by_label.update({label: handle for handle, label in zip(handles, labels)})
    fig.legend(handles_by_label.values(), handles_by_label.keys(), loc="upper center", ncol=3, frameon=False, fontsize=8)
    fig.supxlabel("Total cost", y=0.02)
    fig.supylabel("Makespan", x=0.02)
    fig.tight_layout(rect=(0.03, 0.04, 1.0, 0.95))
    fig.savefig(out_path)
    plt.close(fig)


def build_algorithm_fronts(experiment_dir: str | Path, out_dir: str | Path | None = None) -> Path:
    exp_dir = Path(experiment_dir)
    if not exp_dir.is_absolute():
        exp_dir = ROOT / exp_dir
    out_path = Path(out_dir) if out_dir is not None else exp_dir / "pareto" / "algorithm_front_plots"
    if not out_path.is_absolute():
        out_path = ROOT / out_path

    all_rows = read_csv(exp_dir / "pareto" / "all_pareto_points.csv")
    by_instance: dict[str, list[dict]] = {}
    for row in all_rows:
        instance = str(row.get("instance", ""))
        if instance:
            by_instance.setdefault(instance, []).append(row)

    summary = []
    for instance, rows in sorted(by_instance.items()):
        short = _short_instance(instance)
        instance_dir = out_path / "by_instance"
        figure_path = instance_dir / f"{short}_algorithm_pareto_fronts.png"
        _plot_algorithm_instance(rows, figure_path, f"{short} algorithm on/off all-seed Pareto fronts")
        write_csv(instance_dir / f"{short}_algorithm_pareto_points.csv", rows)
        summary.append(
            {
                "instance": instance,
                "short_instance": short,
                "input_points": len(rows),
                "figure_path": figure_path.as_posix(),
                "csv_path": (instance_dir / f"{short}_algorithm_pareto_points.csv").as_posix(),
            }
        )
    write_csv(out_path / "algorithm_pareto_front_summary.csv", summary)
    _plot_all_instances(by_instance, out_path / "all_instances_algorithm_pareto_fronts.png")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-instance algorithm Pareto-front comparison plots.")
    parser.add_argument("--experiment-dir", default="reports/mvc_mk01_15_formal_2obj/main_experiment")
    parser.add_argument("--out-dir", default=None, help="Default: <experiment-dir>/pareto/algorithm_front_plots.")
    args = parser.parse_args()
    out_dir = build_algorithm_fronts(args.experiment_dir, args.out_dir)
    print(f"algorithm_fronts_dir: {out_dir.as_posix()}")
    print(f"summary: {(out_dir / 'algorithm_pareto_front_summary.csv').as_posix()}")


if __name__ == "__main__":
    main()
