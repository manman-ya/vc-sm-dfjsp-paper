from __future__ import annotations

import argparse
from pathlib import Path
from typing import Mapping, Sequence

from mvc_experiment_utils import ROOT, read_csv, write_csv
from smdfjsp.metrics.multiobjective import get_non_dominated_indices


def _short_instance(name: str) -> str:
    return name.split("_mvc_", 1)[0]


def _float(row: Mapping[str, object], key: str) -> float:
    return float(row[key])  # type: ignore[index]


def _merge_duplicate_objectives(rows: Sequence[dict]) -> list[dict]:
    grouped: dict[tuple[float, float], list[dict]] = {}
    for row in rows:
        key = (round(float(row["total_cost"]), 8), round(float(row["makespan"]), 8))
        grouped.setdefault(key, []).append(row)

    merged = []
    for (total_cost, makespan), items in sorted(grouped.items()):
        representative = dict(sorted(items, key=lambda r: (str(r.get("algorithm", "")), str(r.get("seed", ""))))[0])
        representative["total_cost"] = total_cost
        representative["makespan"] = makespan
        representative["support_algorithms"] = ",".join(sorted({str(r.get("algorithm", "")) for r in items}))
        representative["support_cross_modes"] = ",".join(sorted({str(r.get("cross_chain", "")) for r in items}))
        representative["support_seeds"] = ",".join(sorted({str(r.get("seed", "")) for r in items}))
        representative["support_run_count"] = len(items)
        merged.append(representative)
    return merged


def _non_dominated(rows: Sequence[dict]) -> list[dict]:
    unique = _merge_duplicate_objectives(rows)
    objs = [(_float(row, "total_cost"), _float(row, "makespan")) for row in unique]
    nd_indices = get_non_dominated_indices(objs)
    return sorted((unique[i] for i in nd_indices), key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))


def _matching_objective_rows(rows: Sequence[dict], target: Mapping[str, object]) -> list[dict]:
    target_key = (round(float(target["total_cost"]), 8), round(float(target["makespan"]), 8))
    return [
        row
        for row in rows
        if (round(float(row["total_cost"]), 8), round(float(row["makespan"]), 8)) == target_key
    ]


def _annotate_on_cross_support(rows: Sequence[dict], source_rows: Sequence[dict]) -> list[dict]:
    annotated = []
    for row in rows:
        support_rows = _matching_objective_rows(source_rows, row)
        on_rows = [r for r in support_rows if str(r.get("cross_chain", "")) == "on"]
        on_real = [r for r in on_rows if float(r.get("cross_chain_jobs") or 0.0) > 0.0]
        item = dict(row)
        item["on_support_run_count"] = len(on_rows)
        item["on_real_cross_run_count"] = len(on_real)
        item["on_max_cross_chain_jobs"] = max((float(r.get("cross_chain_jobs") or 0.0) for r in on_rows), default=0.0)
        item["on_max_cross_chain_ratio"] = max((float(r.get("cross_chain_ratio") or 0.0) for r in on_rows), default=0.0)
        item["on_support_algorithms"] = ",".join(sorted({str(r.get("algorithm", "")) for r in on_rows}))
        item["on_support_seeds"] = ",".join(sorted({str(r.get("seed", "")) for r in on_rows}))
        item["on_cross_chain_flows"] = " | ".join(sorted({str(r.get("cross_chain_flow", "")) for r in on_real if r.get("cross_chain_flow")}))
        annotated.append(item)
    return annotated


def _plot_single_mode(rows: Sequence[dict], out_path: Path, title: str) -> None:
    if not rows:
        return
    import matplotlib.pyplot as plt

    out_path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows, key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))
    fig, ax = plt.subplots(figsize=(7, 4.6), dpi=160)
    x = [_float(r, "total_cost") for r in ordered]
    y = [_float(r, "makespan") for r in ordered]
    ax.plot(x, y, marker="o", linewidth=1.5, markersize=4)
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Makespan")
    ax.set_title(title)
    ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _mode_key(row: Mapping[str, object]) -> str:
    support = str(row.get("support_cross_modes", row.get("cross_chain", "")))
    if support == "off,on":
        return "off+on"
    return support


def _plot_on_off(rows: Sequence[dict], out_path: Path, title: str) -> None:
    if not rows:
        return
    import matplotlib.pyplot as plt

    colors = {"off": "#4c78a8", "on": "#e15759", "off+on": "#7f3c8d"}
    labels = {"off": "off only", "on": "on only", "off+on": "off+on"}
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7.4, 4.8), dpi=160)
    ordered = sorted(rows, key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))
    ax.plot(
        [_float(r, "total_cost") for r in ordered],
        [_float(r, "makespan") for r in ordered],
        color="#777777",
        linewidth=1.2,
        alpha=0.55,
        zorder=1,
    )
    for mode in ("off", "on", "off+on"):
        mode_rows = [r for r in ordered if _mode_key(r) == mode]
        if not mode_rows:
            continue
        ax.scatter(
            [_float(r, "total_cost") for r in mode_rows],
            [_float(r, "makespan") for r in mode_rows],
            s=28,
            color=colors[mode],
            label=f"{labels[mode]} (n={len(mode_rows)})",
            zorder=2,
        )
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Makespan")
    ax.set_title(title)
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def _plot_all_instances(instance_rows: Mapping[str, Sequence[dict]], out_path: Path) -> None:
    import math
    import matplotlib.pyplot as plt

    colors = {"off": "#4c78a8", "on": "#e15759", "off+on": "#7f3c8d"}
    instances = sorted(instance_rows)
    if not instances:
        return
    cols = 3
    rows_n = math.ceil(len(instances) / cols)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(rows_n, cols, figsize=(cols * 5.0, rows_n * 3.6), dpi=160)
    axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]

    for ax, instance in zip(axes_list, instances):
        rows = sorted(instance_rows[instance], key=lambda r: (_float(r, "total_cost"), _float(r, "makespan")))
        if rows:
            ax.plot(
                [_float(r, "total_cost") for r in rows],
                [_float(r, "makespan") for r in rows],
                color="#777777",
                linewidth=1.0,
                alpha=0.5,
            )
        for mode in ("off", "on", "off+on"):
            mode_rows = [r for r in rows if _mode_key(r) == mode]
            if not mode_rows:
                continue
            ax.scatter(
                [_float(r, "total_cost") for r in mode_rows],
                [_float(r, "makespan") for r in mode_rows],
                s=12,
                color=colors[mode],
                label=mode,
                zorder=2,
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
    fig.legend(handles_by_label.values(), handles_by_label.keys(), loc="upper center", ncol=3, frameon=False)
    fig.supxlabel("Total cost", y=0.02)
    fig.supylabel("Makespan", x=0.02)
    fig.tight_layout(rect=(0.03, 0.04, 1.0, 0.95))
    fig.savefig(out_path)
    plt.close(fig)


def build_instance_nd_fronts(experiment_dir: str | Path, out_dir: str | Path | None = None) -> Path:
    exp_dir = Path(experiment_dir)
    if not exp_dir.is_absolute():
        exp_dir = ROOT / exp_dir
    if out_dir is None:
        out_path = exp_dir / "pareto" / "combined_front_plots"
    else:
        out_path = Path(out_dir)
        if not out_path.is_absolute():
            out_path = ROOT / out_path

    all_rows = read_csv(exp_dir / "pareto" / "all_pareto_points.csv")
    by_instance_mode: dict[str, dict[str, list[dict]]] = {}
    for row in all_rows:
        instance = str(row.get("instance", ""))
        mode = str(row.get("cross_chain", ""))
        if mode not in {"off", "on"}:
            continue
        by_instance_mode.setdefault(instance, {}).setdefault(mode, []).append(row)

    summary = []
    combined_summary = []
    instance_global_nd: dict[str, list[dict]] = {}
    for instance, modes in sorted(by_instance_mode.items()):
        short = _short_instance(instance)
        for mode in ("off", "on"):
            input_rows = modes.get(mode, [])
            nd_rows = _non_dominated(input_rows)
            write_csv(out_path / "csv" / "per_mode_nd" / f"{short}_{mode}_all_seed_nd.csv", nd_rows)
            _plot_single_mode(
                nd_rows,
                out_path / "figures" / "per_mode_nd" / f"{short}_{mode}_all_seed_nd.png",
                f"{short} {mode} all-seed non-dominated front",
            )
            summary.append(
                {
                    "instance": instance,
                    "short_instance": short,
                    "cross_chain": mode,
                    "input_points": len(input_rows),
                    "nd_points": len(nd_rows),
                    "min_total_cost": min((_float(r, "total_cost") for r in nd_rows), default=""),
                    "min_makespan": min((_float(r, "makespan") for r in nd_rows), default=""),
                    "algorithms": ",".join(sorted({str(r.get("algorithm", "")) for r in input_rows})),
                    "seeds": ",".join(sorted({str(r.get("seed", "")) for r in input_rows})),
                }
            )

        merged_input_rows = modes.get("off", []) + modes.get("on", [])
        global_nd_rows = [
            dict(row, nd_scope="on_off_global")
            for row in _annotate_on_cross_support(_non_dominated(merged_input_rows), merged_input_rows)
        ]
        instance_global_nd[instance] = global_nd_rows
        nested_csv = out_path / "csv" / "on_off_nd" / f"{short}_on_off_all_seed_nd.csv"
        nested_png = out_path / "figures" / "on_off_nd" / f"{short}_on_off_all_seed_nd.png"
        # Keep root-level export filenames short enough for Windows path limits.
        flat_prefix = short.removesuffix("_merged")
        flat_stem = f"{flat_prefix}_merged_on_off_nondominated_front"
        flat_csv = out_path / f"{flat_stem}.csv"
        flat_png = out_path / f"{flat_stem}.png"
        write_csv(nested_csv, global_nd_rows)
        write_csv(flat_csv, global_nd_rows)
        _plot_on_off(
            global_nd_rows,
            nested_png,
            f"{short} merged on/off all-seed non-dominated front",
        )
        _plot_on_off(
            global_nd_rows,
            flat_png,
            f"{short} merged on/off all-seed non-dominated front",
        )
        off_only = sum(1 for r in global_nd_rows if _mode_key(r) == "off")
        on_only = sum(1 for r in global_nd_rows if _mode_key(r) == "on")
        both_modes = sum(1 for r in global_nd_rows if _mode_key(r) == "off+on")
        combined_summary.append(
            {
                "short_instance": short,
                "input_points": len(merged_input_rows),
                "unique_input_points": len(_merge_duplicate_objectives(merged_input_rows)),
                "nd_points": len(global_nd_rows),
                "off_only_points": off_only,
                "on_only_points": on_only,
                "off_on_points": both_modes,
                "figure_path": flat_png.as_posix(),
                "csv_path": flat_csv.as_posix(),
            }
        )
        summary.append(
            {
                "instance": instance,
                "short_instance": short,
                "cross_chain": "off+on",
                "input_points": len(merged_input_rows),
                "nd_points": len(global_nd_rows),
                "min_total_cost": min((_float(r, "total_cost") for r in global_nd_rows), default=""),
                "min_makespan": min((_float(r, "makespan") for r in global_nd_rows), default=""),
                "algorithms": ",".join(sorted({str(r.get("algorithm", "")) for r in merged_input_rows})),
                "seeds": ",".join(sorted({str(r.get("seed", "")) for r in merged_input_rows})),
            }
        )

    write_csv(out_path / "summary" / "per_instance_nd_summary.csv", summary)
    write_csv(out_path / "merged_on_off_nondominated_front_summary.csv", combined_summary)
    _plot_all_instances(instance_global_nd, out_path / "figures" / "all_instances_on_off_all_seed_nd.png")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-instance all-seed non-dominated fronts for MVC experiments.")
    parser.add_argument(
        "--experiment-dir",
        default="reports/mvc_mk01_15_formal_2obj/main_experiment",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Default: <experiment-dir>/pareto/combined_front_plots.",
    )
    args = parser.parse_args()

    out_dir = build_instance_nd_fronts(args.experiment_dir, args.out_dir)
    print(f"out_dir: {out_dir.as_posix()}")
    print(f"summary: {(out_dir / 'summary' / 'per_instance_nd_summary.csv').as_posix()}")
    print(f"on_off_figures: {(out_dir / 'figures' / 'on_off_nd').as_posix()}")


if __name__ == "__main__":
    main()
