from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from smdfjsp.core.mvc_types import MVCJob, MVCModeConfig, MVCSMDFJSPInstance, MVCSRU
from smdfjsp.core.types import Operation, ProcessOption


def _id_number(raw_id: object, prefix: str) -> int:
    text = str(raw_id)
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return int(text)


def _labels(items: Iterable[dict], key: str = "id") -> List[str]:
    return [str(x[key]) for x in items]


def get_intra_chain_srus(job: MVCJob, instance: MVCSMDFJSPInstance) -> List[int]:
    return [
        s.sru_id
        for s in instance.srus
        if job.type_id in s.service_type_ids and s.value_chain_id == job.value_chain_id
    ]


def get_cross_chain_srus(job: MVCJob, instance: MVCSMDFJSPInstance) -> List[int]:
    return [
        s.sru_id
        for s in instance.srus
        if job.type_id in s.service_type_ids and s.value_chain_id != job.value_chain_id
    ]


def get_candidate_srus(
    job: MVCJob,
    instance: MVCSMDFJSPInstance,
    cross_chain_allowed: bool | MVCModeConfig = True,
) -> List[int]:
    if isinstance(cross_chain_allowed, MVCModeConfig):
        cross_chain_allowed = cross_chain_allowed.cross_chain_allowed
    intra = get_intra_chain_srus(job, instance)
    if not cross_chain_allowed:
        return intra
    return intra + get_cross_chain_srus(job, instance)


def validate_mvc_instance(instance: MVCSMDFJSPInstance) -> None:
    sru_map = instance.sru_map()
    for sru in instance.srus:
        if not sru.value_chain_id:
            raise ValueError(f"SRU {sru.sru_id} missing value_chain_id")
        if not sru.service_type_ids:
            raise ValueError(f"SRU {sru.sru_id} missing service types")
        if not sru.open_to_cross_chain:
            raise ValueError("All SRUs are expected to be open in the base MVC model")

    for job in instance.jobs:
        if not job.value_chain_id:
            raise ValueError(f"Job {job.job_id} missing value_chain_id")
        if not job.type_label:
            raise ValueError(f"Job {job.job_id} missing type_id")
        intra = get_intra_chain_srus(job, instance)
        if not intra:
            raise ValueError(f"Job {job.job_id} has no intra-chain same-type SRU")
        cross = get_cross_chain_srus(job, instance)
        for sid in intra + cross:
            sru = sru_map[sid]
            if job.type_id not in sru.service_type_ids:
                raise ValueError(f"Job {job.job_id} candidate SRU {sid} is not same type")
            key = (job.job_id, sid)
            if key not in instance.transport_time:
                raise ValueError(f"Missing transport_time for job {job.job_id}, SRU {sid}")
            if key not in instance.transport_cost:
                raise ValueError(f"Missing transport_cost for job {job.job_id}, SRU {sid}")
            if key not in instance.cross_chain_fixed_cost:
                raise ValueError(f"Missing cross fixed cost for job {job.job_id}, SRU {sid}")
            if key not in instance.cross_chain_cost_rate:
                raise ValueError(f"Missing cross cost-rate metadata for job {job.job_id}, SRU {sid}")


def load_mvc_instance_json(path: str | Path, validate: bool = True) -> MVCSMDFJSPInstance:
    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("problem_type") != "MVC-SM-DFJSP":
        raise ValueError("Input JSON is not MVC-SM-DFJSP")

    type_labels = _labels(data.get("types", [])) or sorted(data.get("candidate_srus_by_type", {}).keys())
    type_to_int = {label: idx for idx, label in enumerate(type_labels, start=1)}

    sru_str_to_int: Dict[str, int] = {}
    machine_str_to_int: Dict[str, int] = {}
    machine_cursor = 1
    srus: List[MVCSRU] = []
    for idx, raw in enumerate(data["srus"], start=1):
        sru_label = str(raw["id"])
        sru_str_to_int[sru_label] = idx
        type_label = str(raw["type"])
        machine_ids: List[int] = []
        for m in raw.get("machines", []):
            mid_label = str(m.get("global_machine_id", f"{sru_label}_{m.get('local_machine_id')}"))
            if mid_label not in machine_str_to_int:
                machine_str_to_int[mid_label] = machine_cursor
                machine_cursor += 1
            machine_ids.append(machine_str_to_int[mid_label])
        srus.append(
            MVCSRU(
                sru_id=idx,
                type_id=type_to_int[type_label],
                type_label=type_label,
                value_chain_id=str(raw["value_chain"]),
                machine_ids=machine_ids,
                service_type_ids=[type_to_int[type_label]],
                service_type_labels=[type_label],
                open_to_cross_chain=bool(raw.get("open_to_cross_chain", True)),
            )
        )

    jobs: List[MVCJob] = []
    for raw_job in data["jobs"]:
        job_id = int(raw_job["job_id"])
        type_label = str(raw_job["type"])
        candidate_srus = [_id_number(x, "U") for x in raw_job.get("candidate_srus", [])]
        operations: List[Operation] = []
        for raw_op in raw_job["operations"]:
            options: List[ProcessOption] = []
            by_sru = raw_op["processing_options_by_sru"]
            for sru_label, raw_options in by_sru.items():
                sru_id = sru_str_to_int[str(sru_label)]
                for item in raw_options:
                    mid_label = str(item["global_machine_id"])
                    machine_id = machine_str_to_int[mid_label]
                    options.append(
                        ProcessOption(
                            sru_id=sru_id,
                            machine_id=machine_id,
                            process_time=float(item["adjusted_processing_time"]),
                            process_cost_per_time=float(item["unit_processing_cost"]),
                        )
                    )
            operations.append(Operation(op_id=int(raw_op["op_id"]), options=options))
        jobs.append(
            MVCJob(
                job_id=job_id,
                type_id=type_to_int[type_label],
                type_label=type_label,
                value_chain_id=str(raw_job["value_chain"]),
                operations=operations,
                candidate_sru_ids=candidate_srus,
                release_time=float(raw_job.get("release_time", 0.0)),
            )
        )

    transport_time: Dict[Tuple[int, int], float] = {}
    transport_cost: Dict[Tuple[int, int], float] = {}
    cross_fixed: Dict[Tuple[int, int], float] = {}
    cross_rate: Dict[Tuple[int, int], float] = {}
    is_cross: Dict[Tuple[int, int], bool] = {}

    for j_label, sru_values in data.get("transport_time", {}).items():
        job_id = _id_number(j_label, "J")
        for sru_label, value in sru_values.items():
            transport_time[(job_id, sru_str_to_int[str(sru_label)])] = float(value)
    for j_label, sru_values in data.get("transport_cost", {}).items():
        job_id = _id_number(j_label, "J")
        for sru_label, value in sru_values.items():
            transport_cost[(job_id, sru_str_to_int[str(sru_label)])] = float(value)
    for j_label, sru_values in data.get("cross_chain", {}).items():
        job_id = _id_number(j_label, "J")
        for sru_label, info in sru_values.items():
            key = (job_id, sru_str_to_int[str(sru_label)])
            cross_fixed[key] = float(info.get("cross_chain_fixed_cost", 0.0))
            cross_rate[key] = float(info.get("cross_chain_cost_rate", 0.0))
            is_cross[key] = bool(info.get("is_cross_chain", False))

    instance = MVCSMDFJSPInstance(
        name=str(data["instance_name"]),
        num_types=len(type_to_int),
        jobs=jobs,
        srus=srus,
        transport_time=transport_time,
        transport_cost=transport_cost,
        cross_chain_fixed_cost=cross_fixed,
        cross_chain_cost_rate=cross_rate,
        is_cross_chain=is_cross,
        metadata={
            "source_path": str(path.as_posix()),
            "raw": data,
            "mapping": {
                "type_label_to_int": type_to_int,
                "sru_label_to_int": sru_str_to_int,
                "machine_label_to_int": machine_str_to_int,
            },
        },
    )
    if validate:
        validate_mvc_instance(instance)
    return instance


def save_mvc_instance_json(instance: MVCSMDFJSPInstance, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = instance.metadata.get("raw")
    if isinstance(raw, dict):
        path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    payload = {
        "instance_name": instance.name,
        "problem_type": "MVC-SM-DFJSP",
        "n_jobs": instance.num_jobs,
        "n_srus": instance.num_srus,
        "n_types": instance.num_types,
        "jobs": [
            {
                "job_id": j.job_id,
                "value_chain": j.value_chain_id,
                "type": j.type_label,
                "candidate_srus": j.candidate_sru_ids,
            }
            for j in instance.jobs
        ],
        "srus": [
            {
                "id": s.sru_id,
                "value_chain": s.value_chain_id,
                "type": s.type_label,
                "open_to_cross_chain": s.open_to_cross_chain,
            }
            for s in instance.srus
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
