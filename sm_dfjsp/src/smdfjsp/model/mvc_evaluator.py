"""MVC-SM-DFJSP 个体评价器。

评价器回答“一个编码方案好不好”。它把 UA/OS/OP/MS 编码解释成实际排程，
然后计算正式双目标：
- `total_cost = processing_cost + transport_cost + cross_fixed_cost`
- `makespan = max(订单加工完成时间 + 运输时间)`

注意：跨链变动成本、负载标准差、跨链流向等只作为诊断字段返回，
不进入当前正式双目标优化。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import pstdev
from typing import Dict, List, Tuple

from smdfjsp.core.encoding import build_option_index, op_from_ua_os
from smdfjsp.core.mvc_types import MVCEvalResult, MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.types import EncodedIndividual, ScheduleRecord
from smdfjsp.data.mvc_io import get_candidate_srus
from smdfjsp.model.evaluator import validate_os


@dataclass
class EvaluationTracker:
    """目标函数评价次数计数器。

    算法比较实验通常需要限制最大评价次数，而不是只限制迭代代数。
    这个轻量计数器用于在调用评价器时统一扣减预算。
    """

    max_evaluations: int | None = None
    evaluations: int = 0

    @property
    def remaining(self) -> int | None:
        if self.max_evaluations is None:
            return None
        return max(0, int(self.max_evaluations) - int(self.evaluations))

    @property
    def exhausted(self) -> bool:
        return self.max_evaluations is not None and self.evaluations >= self.max_evaluations

    def consume(self) -> None:
        if self.exhausted:
            raise RuntimeError("objective-function evaluation budget exhausted")
        self.evaluations += 1


def _infinite_result(message: str, objective_dim: int) -> MVCEvalResult:
    """构造不可行解结果。

    多目标排序中目标越小越好，因此不可行个体统一赋为 `(inf, inf)`，
    这样它们不会优先进入精英集或非支配档案。
    """

    objectives = (float("inf"), float("inf"))
    return MVCEvalResult(
        objectives=objectives,
        feasible=False,
        records=[],
        total_cost=float("inf"),
        makespan=float("inf"),
        max_sru_load=float("inf"),
        message=message,
    )


def evaluate_mvc_individual(
    instance: MVCSMDFJSPInstance,
    individual: EncodedIndividual,
    mode: MVCModeConfig | None = None,
    tracker: EvaluationTracker | None = None,
) -> MVCEvalResult:
    """评价一个 MVC 编码个体。

    输入个体包含四层编码：
    - UA: 每个订单选择哪个 SRU。
    - OS: 各服务类型内部的订单工序顺序。
    - OP: 由 UA+OS 派生出的每个 SRU 上的工序队列。
    - MS: OP 队列中每道工序选择哪台机器。

    本函数不改变算法机制，只把编码翻译为排程并计算目标值。
    """

    if tracker is not None:
        tracker.consume()
    mode = mode or MVCModeConfig()
    # OS 必须是合法多重集：每个订单出现次数应等于其工序数。
    if not validate_os(instance, individual.os):  # type: ignore[arg-type]
        return _infinite_result("invalid OS multiset", mode.objective_dim)

    # option_index[(job_id, op_id, sru_id)] -> {machine_id: (process_time, cost_rate)}
    # 用它快速判断某工序在指定 SRU/机器上能否加工，以及对应时间和单位成本。
    option_index = build_option_index(instance)  # type: ignore[arg-type]
    job_map = instance.job_map()
    sru_map = instance.sru_map()

    for job in instance.jobs:
        # 先检查 UA 层是否合法。UA 是整个评价的入口，若订单没有分配 SRU，
        # 后续 OP/MS 都没有解释意义。
        sid = individual.ua.get(job.job_id)
        if sid is None:
            return _infinite_result(f"missing UA for job {job.job_id}", mode.objective_dim)
        if sid not in sru_map:
            return _infinite_result(f"unknown SRU {sid}", mode.objective_dim)
        # 这里调用 mvc_io 的统一候选判断，确保跨链开关和同类型约束被严格执行。
        if sid not in get_candidate_srus(job, instance, mode):
            return _infinite_result("cross-chain forbidden or type mismatch", mode.objective_dim)

    # OP 是派生层：如果调用方没有提前构造，就根据 UA+OS 生成每个 SRU 的工序队列。
    if not individual.op:
        individual.op = op_from_ua_os(instance, individual.ua, individual.os)  # type: ignore[arg-type]

    # machine_ready 记录每台机器最早可用时间；job_ready 记录每个订单上一道工序完成时间。
    # 二者共同决定当前工序的最早开工时间。
    machine_ready: Dict[Tuple[int, int], float] = {}
    job_ready: Dict[int, float] = {j.job_id: float(j.release_time) for j in instance.jobs}
    job_processing_cost: Dict[int, float] = {j.job_id: 0.0 for j in instance.jobs}
    sru_loads: Dict[int, float] = {s.sru_id: 0.0 for s in instance.srus}
    records: List[ScheduleRecord] = []
    processing_cost = 0.0

    for sru_id, seq in individual.op.items():
        # MS 向量与该 SRU 的 OP 队列按位置一一对应。
        ms_vec = individual.ms.get(sru_id, [])
        for idx, (job_id, op_id) in enumerate(seq):
            key = (job_id, op_id, sru_id)
            if key not in option_index:
                return _infinite_result("operation cannot be processed by assigned SRU", mode.objective_dim)
            options = option_index[key]
            machine_id = ms_vec[idx] if idx < len(ms_vec) else None
            if machine_id not in options:
                # 如果 MS 缺失或选择了不可加工机器，评价器采用最快机器兜底。
                # 个体修复器通常会避免这种情况，这里是防御性处理。
                machine_id = min(options.keys(), key=lambda m: options[m][0])
            pt, cp = options[machine_id]
            # 工序不能早于订单上一道工序完成时间，也不能早于机器可用时间。
            start = max(job_ready[job_id], machine_ready.get((sru_id, machine_id), 0.0))
            end = start + float(pt)
            # 加工成本 = 加工时间 * 单位时间加工成本。
            op_cost = float(pt) * float(cp)
            job_ready[job_id] = end
            machine_ready[(sru_id, machine_id)] = end
            job_processing_cost[job_id] += op_cost
            processing_cost += op_cost
            sru_loads[sru_id] = sru_loads.get(sru_id, 0.0) + float(pt)
            records.append(
                ScheduleRecord(
                    job_id=job_id,
                    op_id=op_id,
                    sru_id=sru_id,
                    machine_id=int(machine_id),
                    start=float(start),
                    end=float(end),
                )
            )

    transport_cost = 0.0
    cross_fixed_cost = 0.0
    cross_variable_cost = 0.0
    makespan = 0.0
    cross_count = 0
    flow: Dict[Tuple[str, str], int] = {}
    inflow: Dict[str, int] = {}
    outflow: Dict[str, int] = {}

    for job_id, complete_time in job_ready.items():
        # 每个订单加工完成后还需要按 UA 选择的 SRU 计入运输时间和运输成本。
        sid = individual.ua[job_id]
        key = (job_id, sid)
        if key not in instance.transport_time or key not in instance.transport_cost:
            return _infinite_result("transport miss", mode.objective_dim)
        job = job_map[job_id]
        sru = sru_map[sid]
        transport_cost += float(instance.transport_cost[key])
        # makespan 使用“加工完工 + 运输时间”的最大值，而不是仅看车间内加工结束。
        makespan = max(makespan, float(complete_time) + float(instance.transport_time[key]))
        # 是否跨链优先使用输入表 is_cross_chain；若缺失，则根据订单和 SRU 的价值链 id 推断。
        if instance.is_cross_chain.get(key, job.value_chain_id != sru.value_chain_id):
            cross_count += 1
            # 正式总成本只加入跨链固定成本，不加入 cross_chain_cost_rate 派生的变量成本。
            cross_fixed_cost += float(instance.cross_chain_fixed_cost.get(key, 0.0))
            flow_key = (job.value_chain_id, sru.value_chain_id)
            flow[flow_key] = flow.get(flow_key, 0) + 1
            outflow[job.value_chain_id] = outflow.get(job.value_chain_id, 0) + 1
            inflow[sru.value_chain_id] = inflow.get(sru.value_chain_id, 0) + 1

    # 正式目标 1：总成本。注意 cross_variable_cost 保留为 0，只用于兼容历史 CSV 字段。
    total_cost = processing_cost + transport_cost + cross_fixed_cost
    max_sru_load = max(sru_loads.values()) if sru_loads else 0.0
    load_values = [sru_loads.get(s.sru_id, 0.0) for s in instance.srus]
    sru_load_std = float(pstdev(load_values)) if len(load_values) > 1 else 0.0

    vc_loads: Dict[str, float] = {}
    for sid, load in sru_loads.items():
        vc = sru_map[sid].value_chain_id
        vc_loads[vc] = vc_loads.get(vc, 0.0) + load
    vc_load_std = float(pstdev(list(vc_loads.values()))) if len(vc_loads) > 1 else 0.0

    # 正式目标 2：最大完工时间。两个目标都按“越小越好”处理。
    objectives = (float(total_cost), float(makespan))

    if not all(math.isfinite(x) for x in objectives):
        return _infinite_result("non-finite objectives", mode.objective_dim)

    return MVCEvalResult(
        objectives=objectives,
        feasible=True,
        records=records,
        total_cost=float(total_cost),
        makespan=float(makespan),
        max_sru_load=float(max_sru_load),
        cost_breakdown={
            # 以下拆分帮助解释 total_cost 的来源；Pareto 排序只使用 objectives。
            "processing_cost": float(processing_cost),
            "transport_cost": float(transport_cost),
            "cross_fixed_cost": float(cross_fixed_cost),
            # Kept as a compatibility column for historical result CSVs; the
            # formal two-objective model uses fixed cross-chain cost only.
            "cross_variable_cost": float(cross_variable_cost),
            "total_cost": float(total_cost),
        },
        sru_loads={int(k): float(v) for k, v in sru_loads.items()},
        diagnostics={
            # diagnostics 不参与优化目标，只用于结果分析、消融解释和绘图。
            "cross_chain_jobs": int(cross_count),
            "cross_chain_ratio": float(cross_count / max(len(instance.jobs), 1)),
            "intra_chain_jobs": int(len(instance.jobs) - cross_count),
            "sru_load_std": sru_load_std,
            "value_chain_load_std": vc_load_std,
            "cross_chain_flow": {f"{a}->{b}": n for (a, b), n in flow.items()},
            "value_chain_inflow": inflow,
            "value_chain_outflow": outflow,
        },
    )


def evaluate_mvc_population(
    instance: MVCSMDFJSPInstance,
    pop: List[EncodedIndividual],
    mode: MVCModeConfig,
    tracker: EvaluationTracker | None = None,
) -> None:
    """批量评价种群，并把结果回写到个体对象中。

    主算法后续的非支配排序、精英选择和档案更新都读取 `ind.objectives`
    与 `ind.feasible`，详细评价结果缓存在 `ind.aux["mvc_eval"]`。
    """

    for ind in pop:
        result = evaluate_mvc_individual(instance, ind, mode, tracker)
        ind.objectives = result.objectives  # type: ignore[assignment]
        ind.feasible = result.feasible
        ind.aux["mvc_eval"] = result
