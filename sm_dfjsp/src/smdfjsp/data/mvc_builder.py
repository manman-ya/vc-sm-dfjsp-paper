from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

from smdfjsp.data.mk_parser import MKInstance, parse_mk_file
from smdfjsp.data.mvc_io import load_mvc_instance_json, validate_mvc_instance


@dataclass(frozen=True)
class MVCBuildConfig:
    n_value_chains: int = 3
    n_types: int = 2
    n_srus: int = 6
    seed: int = 20260428
    cross_chain_fixed_cost: float = 20.0
    cross_chain_cost_rate: float = 0.0
    transport_unit_cost: float = 3.0


BASE_MACHINE_COSTS = [6.0, 5.0, 7.0, 8.0, 7.5, 6.5, 8.5, 9.0, 5.5, 6.8]
EFFICIENCY_PATTERN = [1.00, 0.95, 0.90, 1.05, 0.92, 1.10, 0.98, 1.08, 0.88, 1.02]
COST_PATTERN = [1.00, 1.10, 1.20, 0.95, 1.15, 0.90, 1.05, 0.98, 1.18, 0.92]


def _split_balanced(ids: List[int], n_groups: int) -> Dict[str, List[int]]:
    groups = {f"VC{i + 1}": [] for i in range(n_groups)}
    for pos, item in enumerate(ids):
        groups[f"VC{pos % n_groups + 1}"].append(item)
    return groups


def _assign_types_by_operation_count(mk: MKInstance, n_types: int) -> Dict[str, List[int]]:
    ordered = sorted(mk.jobs, key=lambda j: (len(j.operations), j.job_id))
    groups = {f"T{i + 1}": [] for i in range(n_types)}
    for pos, job in enumerate(ordered):
        groups[f"T{pos * n_types // max(len(ordered), 1) + 1}"].append(job.job_id)
    return {k: sorted(v) for k, v in groups.items()}


def _job_lookup(groups: Dict[str, List[int]]) -> Dict[int, str]:
    return {job_id: label for label, jobs in groups.items() for job_id in jobs}


def _build_sru_specs(cfg: MVCBuildConfig, num_machines: int) -> Tuple[List[dict], Dict[str, str], Dict[str, str]]:
    min_required = cfg.n_value_chains * cfg.n_types
    if cfg.n_srus < min_required:
        raise ValueError(f"n_srus={cfg.n_srus} is too small; need at least {min_required}")
    specs: List[Tuple[str, str, str]] = []
    for vc_i in range(1, cfg.n_value_chains + 1):
        for t_i in range(1, cfg.n_types + 1):
            specs.append((f"U{len(specs) + 1}", f"VC{vc_i}", f"T{t_i}"))
    cursor = 0
    while len(specs) < cfg.n_srus:
        vc = f"VC{cursor % cfg.n_value_chains + 1}"
        typ = f"T{cursor % cfg.n_types + 1}"
        specs.append((f"U{len(specs) + 1}", vc, typ))
        cursor += 1

    srus: List[dict] = []
    sru_to_vc: Dict[str, str] = {}
    sru_to_type: Dict[str, str] = {}
    for idx, (sru_id, vc, typ) in enumerate(specs):
        eff = EFFICIENCY_PATTERN[idx % len(EFFICIENCY_PATTERN)]
        cost_factor = COST_PATTERN[idx % len(COST_PATTERN)]
        machines = []
        for base_mid in range(num_machines):
            base_cost = BASE_MACHINE_COSTS[base_mid % len(BASE_MACHINE_COSTS)]
            machines.append(
                {
                    "local_machine_id": f"M{base_mid}",
                    "global_machine_id": f"{sru_id}_M{base_mid}",
                    "base_machine_id": base_mid,
                    "unit_processing_cost": float(round(base_cost * cost_factor, 6)),
                }
            )
        srus.append(
            {
                "id": sru_id,
                "value_chain": vc,
                "type": typ,
                "open_to_cross_chain": True,
                "efficiency_factor": float(eff),
                "cost_factor": float(cost_factor),
                "machines": machines,
            }
        )
        sru_to_vc[sru_id] = vc
        sru_to_type[sru_id] = typ
    return srus, sru_to_vc, sru_to_type


def _transport_base(job_vc: str, sru_vc: str) -> int:
    j = int(job_vc.replace("VC", ""))
    s = int(sru_vc.replace("VC", ""))
    if j == s:
        return 3
    return 7 + 2 * abs(j - s)


def build_mvc_instance(mk_path: str | Path, cfg: MVCBuildConfig) -> dict:
    mk = parse_mk_file(mk_path)
    rng = np.random.default_rng(cfg.seed + sum(ord(c) for c in mk.name))
    job_ids = [job.job_id for job in mk.jobs]
    value_chains = _split_balanced(job_ids, cfg.n_value_chains)
    types = _assign_types_by_operation_count(mk, cfg.n_types)
    job_to_vc = _job_lookup(value_chains)
    job_to_type = _job_lookup(types)
    srus, sru_to_vc, sru_to_type = _build_sru_specs(cfg, mk.num_machines)
    sru_map = {str(s["id"]): s for s in srus}
    candidate_srus_by_type: Dict[str, List[str]] = {
        f"T{i}": [sid for sid, typ in sru_to_type.items() if typ == f"T{i}"]
        for i in range(1, cfg.n_types + 1)
    }

    jobs_payload: List[dict] = []
    compatibility: Dict[str, dict] = {}
    for mk_job in mk.jobs:
        jid = mk_job.job_id
        vc = job_to_vc[jid]
        typ = job_to_type[jid]
        all_type_srus = candidate_srus_by_type[typ]
        intra = [sid for sid in all_type_srus if sru_to_vc[sid] == vc]
        cross = [sid for sid in all_type_srus if sru_to_vc[sid] != vc]
        candidates = intra + cross
        operations: List[dict] = []
        for op_idx, mk_op in enumerate(mk_job.operations, start=1):
            eligible = [
                {"base_machine_id": int(machine_id - 1), "base_processing_time": int(process_time)}
                for machine_id, process_time in mk_op.options
            ]
            proc_by_sru: Dict[str, List[dict]] = {}
            for sid in candidates:
                sru = sru_map[sid]
                eff = float(sru["efficiency_factor"])
                opts: List[dict] = []
                for item in eligible:
                    base_mid = int(item["base_machine_id"])
                    base_pt = int(item["base_processing_time"])
                    noise = float(rng.uniform(0.95, 1.05))
                    adjusted = max(1, int(math.ceil(base_pt * eff * noise)))
                    machine_obj = sru["machines"][base_mid]
                    opts.append(
                        {
                            "global_machine_id": machine_obj["global_machine_id"],
                            "base_machine_id": base_mid,
                            "base_processing_time": base_pt,
                            "adjusted_processing_time": adjusted,
                            "unit_processing_cost": float(machine_obj["unit_processing_cost"]),
                        }
                    )
                proc_by_sru[sid] = opts
            operations.append(
                {
                    "op_id": op_idx,
                    "op_id_zero_based": op_idx - 1,
                    "eligible_base_machines": eligible,
                    "processing_options_by_sru": proc_by_sru,
                }
            )
        jobs_payload.append(
            {
                "job_id": jid,
                "job_id_zero_based": jid - 1,
                "value_chain": vc,
                "type": typ,
                "release_time": 0,
                "n_operations": len(mk_job.operations),
                "candidate_srus": candidates,
                "operations": operations,
            }
        )
        compatibility[f"J{jid}"] = {
            "candidate_srus": candidates,
            "intra_chain_srus": intra,
            "cross_chain_srus": cross,
        }

    transport_time: Dict[str, Dict[str, int]] = {}
    transport_cost: Dict[str, Dict[str, float]] = {}
    cross_chain: Dict[str, Dict[str, dict]] = {}
    for job in jobs_payload:
        jkey = f"J{job['job_id']}"
        job_vc = str(job["value_chain"])
        transport_time[jkey] = {}
        transport_cost[jkey] = {}
        cross_chain[jkey] = {}
        for sid in job["candidate_srus"]:
            sru_vc = sru_to_vc[sid]
            t = int(_transport_base(job_vc, sru_vc) + rng.integers(0, 3))
            transport_time[jkey][sid] = t
            transport_cost[jkey][sid] = float(round(t * cfg.transport_unit_cost, 6))
            is_cross = job_vc != sru_vc
            cross_chain[jkey][sid] = {
                "job_value_chain": job_vc,
                "sru_value_chain": sru_vc,
                "is_cross_chain": bool(is_cross),
                "cross_chain_fixed_cost": float(cfg.cross_chain_fixed_cost if is_cross else 0.0),
                "cross_chain_cost_rate": 0.0,
                "estimated_cross_chain_cost": float(
                    round(cfg.cross_chain_fixed_cost if is_cross else 0.0, 6)
                ),
            }

    payload = {
        "instance_name": f"{mk.name}_mvc_{cfg.n_value_chains}vc_{cfg.n_types}type_{cfg.n_srus}sru",
        "source_instance": mk.name,
        "problem_type": "MVC-SM-DFJSP",
        "is_dynamic": False,
        "release_time_policy": "all_zero",
        "seed": int(cfg.seed),
        "n_jobs": mk.num_jobs,
        "n_base_machines": mk.num_machines,
        "n_value_chains": cfg.n_value_chains,
        "n_types": cfg.n_types,
        "n_srus": cfg.n_srus,
        "value_chains": [
            {"id": label, "name": f"价值链{label.replace('VC', '')}", "jobs": jobs}
            for label, jobs in value_chains.items()
        ],
        "types": [
            {"id": label, "name": f"服务类型{label.replace('T', '')}", "jobs": jobs}
            for label, jobs in types.items()
        ],
        "base_machines": [
            {
                "local_machine_id": f"M{i}",
                "base_machine_id": i,
                "base_unit_processing_cost": BASE_MACHINE_COSTS[i % len(BASE_MACHINE_COSTS)],
            }
            for i in range(mk.num_machines)
        ],
        "jobs": jobs_payload,
        "srus": srus,
        "candidate_srus_by_type": candidate_srus_by_type,
        "job_sru_compatibility": compatibility,
        "transport_time": transport_time,
        "transport_cost": transport_cost,
        "cross_chain": cross_chain,
        "objectives": [
            {"id": "total_cost", "sense": "min", "definition": "PC + TC + CFC"},
            {"id": "makespan", "sense": "min", "definition": "max(C_j + transport_time)"},
        ],
        "diagnostics": ["max_sru_load", "sru_load_std", "cross_chain_ratio", "cross_chain_flow"],
        "notes": {
            "source_mk_file": str(Path(mk_path).as_posix()),
            "static_orders_only": True,
            "all_release_time_zero": True,
            "job_single_sru_hard_constraint": True,
            "operations_keep_original_order": True,
            "all_srus_open_to_cross_chain": True,
            "cross_chain_allowed_is_experiment_mode": True,
            "transport_unit_cost": cfg.transport_unit_cost,
        },
    }
    return payload


def save_mvc_payload(payload: dict, output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_mvc_json_file(path: str | Path) -> None:
    inst = load_mvc_instance_json(path)
    validate_mvc_instance(inst)


def write_dataset_readme(output_dir: str | Path, cfg: MVCBuildConfig) -> None:
    output_dir = Path(output_dir)
    text = f"""# MVC-SM-DFJSP Dataset

Generated from MK/FJSP benchmark files.

- Value chains represent fixed order-level business ownership.
- Service types represent fixed order-level manufacturing demand classes.
- All SRUs are open to shared manufacturing collaboration.
- `cross_chain_allowed` is an experiment mode, not a data openness field.
- Intra-chain choices and cross-chain choices must both match service type.
- Transport cost is generated as `transport_time * {cfg.transport_unit_cost}`.
- Cross-chain collaboration cost uses fixed cost `{cfg.cross_chain_fixed_cost}` only; variable rate is always 0.
"""
    (output_dir / "README.md").write_text(text, encoding="utf-8")


def build_mvc_dataset(
    mk_dir: str | Path,
    output_dir: str | Path,
    cfg: MVCBuildConfig,
    pattern: str = "mk*.txt",
) -> List[dict]:
    mk_dir = Path(mk_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: List[dict] = []
    for idx, mk_file in enumerate(sorted(mk_dir.glob(pattern))):
        inst_cfg = MVCBuildConfig(
            n_value_chains=cfg.n_value_chains,
            n_types=cfg.n_types,
            n_srus=cfg.n_srus,
            seed=cfg.seed + idx,
            cross_chain_fixed_cost=cfg.cross_chain_fixed_cost,
            cross_chain_cost_rate=cfg.cross_chain_cost_rate,
            transport_unit_cost=cfg.transport_unit_cost,
        )
        payload = build_mvc_instance(mk_file, inst_cfg)
        out_file = output_dir / f"{payload['source_instance']}_mvc_{cfg.n_value_chains}vc_{cfg.n_types}type_{cfg.n_srus}sru.json"
        save_mvc_payload(payload, out_file)
        validate_mvc_json_file(out_file)
        total_ops = sum(int(j["n_operations"]) for j in payload["jobs"])
        rows.append(
            {
                "instance": payload["instance_name"],
                "source_instance": payload["source_instance"],
                "jobs": payload["n_jobs"],
                "base_machines": payload["n_base_machines"],
                "value_chains": payload["n_value_chains"],
                "types": payload["n_types"],
                "srus": payload["n_srus"],
                "ops": total_ops,
                "seed": payload["seed"],
                "file": out_file.as_posix(),
            }
        )
    with (output_dir / "manifest.csv").open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["instance", "source_instance", "jobs", "base_machines", "value_chains", "types", "srus", "ops", "seed", "file"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    write_dataset_readme(output_dir, cfg)
    return rows
