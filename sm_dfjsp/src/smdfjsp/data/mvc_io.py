"""MVC-SM-DFJSP 的输入输出与候选 SRU 判断。

本文件承担两类职责：
1. 把外部 JSON 中的字符串标签（如 J1、U3、机器全局 id）转换成算法内部使用的整数 id。
2. 根据订单价值链、SRU 价值链和服务类型，判断某订单可选择哪些 SRU。

候选资源判断是 MVC 模型的关键入口：
- 链内候选：同价值链 + 同服务类型。
- 跨链候选：不同价值链 + 同服务类型。
- 最终候选：是否拼接跨链候选由 `MVCModeConfig.cross_chain_allowed` 决定。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from smdfjsp.core.mvc_types import MVCJob, MVCModeConfig, MVCSMDFJSPInstance, MVCSRU
from smdfjsp.core.types import Operation, ProcessOption


def _id_number(raw_id: object, prefix: str) -> int:
    """把带前缀的外部编号转换为整数编号。

    输入 JSON 中可能使用 `J1`、`U2` 这类业务标签；算法内部统一使用整数，
    因为 UA/MS/OP 编码和数组索引都依赖稳定的数值 id。
    """

    text = str(raw_id)
    if text.startswith(prefix):
        text = text[len(prefix) :]
    return int(text)


def _labels(items: Iterable[dict], key: str = "id") -> List[str]:
    """从 JSON 对象列表中抽取标签，保持原始顺序用于建立 type_id 映射。"""

    return [str(x[key]) for x in items]


def get_intra_chain_srus(job: MVCJob, instance: MVCSMDFJSPInstance) -> List[int]:
    """返回订单的链内同类型候选 SRU。

    判断条件有两个，必须同时满足：
    1. `job.type_id in s.service_type_ids`：SRU 能提供订单所需服务类型。
    2. `s.value_chain_id == job.value_chain_id`：SRU 与订单属于同一价值链。

    这组候选是“非跨链模式”下的全部可选资源，也是跨链模式下的基础候选。
    """

    return [
        s.sru_id
        for s in instance.srus
        if job.type_id in s.service_type_ids and s.value_chain_id == job.value_chain_id
    ]


def get_cross_chain_srus(job: MVCJob, instance: MVCSMDFJSPInstance) -> List[int]:
    """返回订单的跨链同类型候选 SRU。

    判断条件同样要求服务类型兼容，但价值链必须不同：
    `s.value_chain_id != job.value_chain_id`。这些 SRU 只有在实验模式允许跨链时
    才会进入 `get_candidate_srus` 的最终候选集。
    """

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
    """按实验模式返回订单最终可选 SRU。

    `cross_chain_allowed` 可以直接传布尔值，也可以传 `MVCModeConfig`。
    这样评价器、初始化和概率模型可以统一调用这个函数，而不必各自重复判断逻辑。

    返回顺序是链内候选在前、跨链候选在后。该顺序本身不代表优先级，
    但有助于调试时先看到“本链是否具备可行资源”。
    """

    if isinstance(cross_chain_allowed, MVCModeConfig):
        cross_chain_allowed = cross_chain_allowed.cross_chain_allowed
    intra = get_intra_chain_srus(job, instance)
    if not cross_chain_allowed:
        return intra
    return intra + get_cross_chain_srus(job, instance)


def validate_mvc_instance(instance: MVCSMDFJSPInstance) -> None:
    """校验 MVC 算例是否满足算法所需的基本数据完整性。

    这里不做调度可行性搜索，只检查静态数据：
    - 每个 SRU 必须有价值链和服务类型。
    - 每个订单必须至少有一个链内同类型 SRU，保证非跨链模式也有可行基础。
    - 对每个链内/跨链同类型候选，都必须给出运输时间、运输成本和跨链元数据。

    如果这些表缺失，后续评价器会无法计算 `total_cost` 或 `makespan`。
    """

    sru_map = instance.sru_map()
    for sru in instance.srus:
        # SRU 没有价值链归属时，无法判断链内/跨链。
        if not sru.value_chain_id:
            raise ValueError(f"SRU {sru.sru_id} missing value_chain_id")
        # 没有服务类型时，任何订单都无法合法选择该 SRU。
        if not sru.service_type_ids:
            raise ValueError(f"SRU {sru.sru_id} missing service types")
        # 当前基础模型假设所有 SRU 对跨链开放；消融实验通过 mode 控制是否允许跨链。
        if not sru.open_to_cross_chain:
            raise ValueError("All SRUs are expected to be open in the base MVC model")

    for job in instance.jobs:
        # 订单缺少价值链时，候选资源和跨链成本都无法判定。
        if not job.value_chain_id:
            raise ValueError(f"Job {job.job_id} missing value_chain_id")
        if not job.type_label:
            raise ValueError(f"Job {job.job_id} missing type_id")
        intra = get_intra_chain_srus(job, instance)
        # 至少一个链内同类型 SRU 是基础可行性要求，避免“必须跨链才可行”的退化数据。
        if not intra:
            raise ValueError(f"Job {job.job_id} has no intra-chain same-type SRU")
        cross = get_cross_chain_srus(job, instance)
        for sid in intra + cross:
            sru = sru_map[sid]
            # 防御性检查：链内/跨链函数本身已经筛过类型，这里用于发现数据或代码不一致。
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
    """从 MVC-SM-DFJSP JSON 文件读取完整算例。

    读取过程分为四步：
    1. 建立服务类型、SRU、机器的字符串标签到整数 id 的映射。
    2. 读取 SRU 表，保留其价值链、服务类型和机器集合。
    3. 读取订单表和每道工序的可选加工方案。
    4. 读取运输与跨链成本矩阵，并组装成 `MVCSMDFJSPInstance`。

    原始 JSON 和映射关系会放进 `metadata`，便于结果导出时还原业务标签。
    """

    path = Path(path)
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("problem_type") != "MVC-SM-DFJSP":
        raise ValueError("Input JSON is not MVC-SM-DFJSP")

    type_labels = _labels(data.get("types", [])) or sorted(data.get("candidate_srus_by_type", {}).keys())
    # type_id 从 1 开始，避免和某些编码中可能使用的 0/空值混淆。
    type_to_int = {label: idx for idx, label in enumerate(type_labels, start=1)}

    sru_str_to_int: Dict[str, int] = {}
    machine_str_to_int: Dict[str, int] = {}
    machine_cursor = 1
    srus: List[MVCSRU] = []
    for idx, raw in enumerate(data["srus"], start=1):
        # SRU 外部标签如 U1/U2 在这里映射为连续整数，后续所有表都复用该映射。
        sru_label = str(raw["id"])
        sru_str_to_int[sru_label] = idx
        type_label = str(raw["type"])
        machine_ids: List[int] = []
        for m in raw.get("machines", []):
            # 机器使用 global_machine_id 做全局去重，保证不同 SRU 下同名机器不会重复编号。
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
        # job_id 通常已经是整数；candidate_srus 若为 U1 形式则只提取数字部分。
        job_id = int(raw_job["job_id"])
        type_label = str(raw_job["type"])
        candidate_srus = [_id_number(x, "U") for x in raw_job.get("candidate_srus", [])]
        operations: List[Operation] = []
        for raw_op in raw_job["operations"]:
            options: List[ProcessOption] = []
            by_sru = raw_op["processing_options_by_sru"]
            for sru_label, raw_options in by_sru.items():
                # 每道工序可能在多个 SRU 上加工；同一个 SRU 内又可能有多台候选机器。
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

    # 以下三张表都使用 (job_id, sru_id) 作为键，与评价器中的 UA 分配直接对齐。
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
            # 固定成本是正式目标的一部分；成本率当前作为元数据保留。
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
    """保存 MVC 算例。

    如果实例保留了原始 JSON (`metadata["raw"]`)，优先原样写回，避免丢失当前代码
    未显式建模的扩展字段。若没有原始 JSON，则写出一个轻量级摘要结构。
    """

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
