from __future__ import annotations

from pathlib import Path
from typing import Mapping, Sequence


def _require_pyplot():
    import matplotlib.pyplot as plt

    return plt


def plot_pareto_csv(rows: Sequence[Mapping[str, object]], out_path: str | Path, title: str = "MVC Pareto") -> None:
    if not rows:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    groups = {}
    for row in rows:
        label = str(row.get("algorithm", row.get("variant", "front")))
        if "cross_chain" in row:
            label = f"{label}-{row['cross_chain']}"
        groups.setdefault(label, []).append(row)
    for label, pts in sorted(groups.items()):
        ax.scatter([float(p["total_cost"]) for p in pts], [float(p["makespan"]) for p in pts], s=26, alpha=0.8, label=label)
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Makespan")
    ax.set_title(title)
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_pareto_3d_projection(rows: Sequence[Mapping[str, object]], out_path: str | Path, title: str = "MVC Pareto 3D") -> None:
    if not rows or "max_sru_load" not in rows[0]:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig = plt.figure(figsize=(8, 6), dpi=150)
    ax = fig.add_subplot(111, projection="3d")
    groups = {}
    for row in rows:
        label = str(row.get("algorithm", row.get("variant", "front")))
        if "cross_chain" in row:
            label = f"{label}-{row['cross_chain']}"
        groups.setdefault(label, []).append(row)
    for label, pts in sorted(groups.items()):
        ax.scatter(
            [float(p["total_cost"]) for p in pts],
            [float(p["makespan"]) for p in pts],
            [float(p["max_sru_load"]) for p in pts],
            s=18,
            alpha=0.75,
            label=label,
        )
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Makespan")
    ax.set_zlabel("Max SRU load")
    ax.set_title(title)
    ax.legend(frameon=False, fontsize=7)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_sru_loads(loads: Mapping[int | str, float], out_path: str | Path, title: str = "SRU Loads") -> None:
    if not loads:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(k) for k in loads.keys()]
    values = [float(v) for v in loads.values()]
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.bar(labels, values, color="#4c78a8")
    ax.set_xlabel("SRU")
    ax.set_ylabel("Load")
    ax.set_title(title)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_cross_chain_flow(flow: Mapping[str, int | float], out_path: str | Path, title: str = "Cross-Chain Flow") -> None:
    if not flow:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(k) for k in flow.keys()]
    values = [float(v) for v in flow.values()]
    fig, ax = plt.subplots(figsize=(max(7, len(labels) * 0.8), 4.5), dpi=150)
    ax.bar(labels, values, color="#e15759")
    ax.set_ylabel("Jobs")
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_gantt(records: Sequence[object], out_path: str | Path, title: str = "MVC Schedule") -> None:
    if not records:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def value(record: object, name: str):
        if isinstance(record, Mapping):
            return record[name]
        return getattr(record, name)

    lanes = sorted({f"U{int(value(r, 'sru_id'))}-M{int(value(r, 'machine_id'))}" for r in records})
    lane_pos = {lane: i for i, lane in enumerate(lanes)}
    fig, ax = plt.subplots(figsize=(10, max(4, len(lanes) * 0.35)), dpi=150)
    for record in records:
        lane = f"U{int(value(record, 'sru_id'))}-M{int(value(record, 'machine_id'))}"
        start = float(value(record, "start"))
        end = float(value(record, "end"))
        job_id = int(value(record, "job_id"))
        ax.barh(lane_pos[lane], end - start, left=start, height=0.72, color=f"C{job_id % 10}", alpha=0.85)
        ax.text(start + (end - start) / 2, lane_pos[lane], f"J{job_id}-O{int(value(record, 'op_id'))}", ha="center", va="center", fontsize=6)
    ax.set_yticks(range(len(lanes)))
    ax.set_yticklabels(lanes)
    ax.set_xlabel("Time")
    ax.set_title(title)
    ax.grid(axis="x", alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_metric_bars(rows: Sequence[Mapping[str, object]], out_path: str | Path, metric: str, title: str) -> None:
    if not rows:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = [str(r.get("label", r.get("algorithm", r.get("variant", i)))) for i, r in enumerate(rows)]
    values = [float(r.get(metric, 0.0)) for r in rows]
    fig, ax = plt.subplots(figsize=(max(7, len(labels) * 0.8), 4.5), dpi=150)
    ax.bar(labels, values, color="#59a14f")
    ax.set_ylabel(metric)
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_history_lines(rows: Sequence[Mapping[str, object]], out_path: str | Path, metric: str, title: str) -> None:
    if not rows:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    groups: dict[str, dict[float, list[float]]] = {}
    for row in rows:
        if metric not in row or "iter" not in row:
            continue
        label = str(row.get("algorithm", row.get("variant", "run")))
        if row.get("variant_code"):
            label = f"{row.get('variant_code')}-{row.get('variant', '')}"
        elif row.get("cross_chain"):
            label = f"{label}-{row.get('cross_chain')}"
        try:
            iteration = float(row["iter"])
            value = float(row[metric])
        except (TypeError, ValueError):
            continue
        groups.setdefault(label, {}).setdefault(iteration, []).append(value)
    if not groups:
        return
    fig, ax = plt.subplots(figsize=(8, 5), dpi=150)
    for label, by_iter in sorted(groups.items()):
        ordered = sorted(by_iter.items())
        xs = [iteration for iteration, _ in ordered]
        ys = [sum(values) / len(values) for _, values in ordered]
        markevery = max(1, len(xs) // 10)
        ax.plot(xs, ys, marker="o", markevery=markevery, markersize=3, linewidth=1.8, label=label)
    ax.set_xlabel("Iteration")
    ax.set_ylabel(f"Mean {metric}")
    ax.set_title(title)
    ax.grid(alpha=0.25, linestyle="--")
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_neighborhood_contribution(rows: Sequence[Mapping[str, object]], out_path: str | Path, title: str = "Neighborhood Contribution") -> None:
    if not rows:
        return
    totals = {}
    for row in rows:
        for key, value in row.items():
            if not str(key).startswith("nh_reward_"):
                continue
            kind = str(key).replace("nh_reward_", "")
            totals[kind] = totals.get(kind, 0.0) + float(value or 0.0)
    if not totals:
        return
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = list(totals.keys())
    values = [totals[k] for k in labels]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 1.0), 4.8), dpi=150)
    ax.bar(labels, values, color="#f28e2b")
    ax.set_ylabel("Reward")
    ax.set_title(title)
    ax.tick_params(axis="x", labelrotation=35)
    ax.grid(axis="y", alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_problem_structure(out_path: str | Path) -> None:
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    labels = ["Value chain", "Service type", "SRU", "Machine", "Operation"]
    fig, ax = plt.subplots(figsize=(10, 2.8), dpi=150)
    ax.axis("off")
    x_positions = [0.08, 0.30, 0.50, 0.70, 0.90]
    for x, label in zip(x_positions, labels):
        ax.text(
            x,
            0.55,
            label,
            ha="center",
            va="center",
            fontsize=11,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "#f2f2f2", "edgecolor": "#4c78a8"},
        )
    for left, right in zip(x_positions, x_positions[1:]):
        ax.annotate("", xy=(right - 0.065, 0.55), xytext=(left + 0.065, 0.55), arrowprops={"arrowstyle": "->", "lw": 1.4})
    ax.text(0.5, 0.86, "MVC-SM-DFJSP problem structure", ha="center", va="center", fontsize=13, weight="bold")
    ax.text(0.5, 0.18, "job -> value-chain ownership -> service matching -> intra/cross-chain SRU -> machine -> operation sequence", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_algorithm_flow(out_path: str | Path) -> None:
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    steps = [
        "MVC-aware\ninitialization",
        "Evaluate\npopulation",
        "ND archive\nupdate",
        "Probability\nmodel update",
        "Sample and\nrepair",
        "Cross-chain\ntabu search",
        "Selection by\nrank/crowding",
    ]
    fig, ax = plt.subplots(figsize=(11, 3.2), dpi=150)
    ax.axis("off")
    x_positions = [0.07, 0.22, 0.36, 0.51, 0.65, 0.79, 0.93]
    for x, label in zip(x_positions, steps):
        ax.text(
            x,
            0.55,
            label,
            ha="center",
            va="center",
            fontsize=9,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": "#ffffff", "edgecolor": "#59a14f"},
        )
    for left, right in zip(x_positions, x_positions[1:]):
        ax.annotate("", xy=(right - 0.055, 0.55), xytext=(left + 0.055, 0.55), arrowprops={"arrowstyle": "->", "lw": 1.2})
    ax.annotate("", xy=(0.09, 0.35), xytext=(0.91, 0.35), arrowprops={"arrowstyle": "->", "lw": 1.0, "connectionstyle": "arc3,rad=-0.25"})
    ax.text(0.5, 0.87, "MVC-EDA-TS workflow", ha="center", va="center", fontsize=13, weight="bold")
    ax.text(0.5, 0.16, "Archive solutions support probability learning and local-search seed selection", ha="center", fontsize=8)
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)


def plot_explanatory_case(out_path: str | Path) -> None:
    plt = _require_pyplot()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {"label": "Intra-chain SRU", "total_cost": 120.0, "makespan": 95.0},
        {"label": "Cross-chain SRU", "total_cost": 168.0, "makespan": 68.0},
        {"label": "Compromise", "total_cost": 145.0, "makespan": 78.0},
    ]
    fig, ax = plt.subplots(figsize=(6.5, 4.5), dpi=150)
    for row in rows:
        ax.scatter(row["total_cost"], row["makespan"], s=70)
        ax.text(row["total_cost"] + 1.5, row["makespan"] + 1.0, row["label"], fontsize=9)
    ax.plot([r["total_cost"] for r in rows], [r["makespan"] for r in rows], linestyle="--", color="#999999", alpha=0.7)
    ax.set_xlabel("Total cost")
    ax.set_ylabel("Makespan")
    ax.set_title("Illustrative cost-time trade-off")
    ax.grid(alpha=0.25, linestyle="--")
    fig.tight_layout()
    fig.savefig(out_path)
    plt.close(fig)
