from __future__ import annotations

"""MVC-EDA-TS 的启发式初始化。

初始种群质量会显著影响 EDA 概率模型的早期学习方向。
这里提供多种简单但有业务含义的初始化策略：
- random: 完全随机，提供探索多样性。
- intra-chain-first: 优先选择同价值链 SRU，减少跨链成本。
- cost-first: 优先选择估计总成本最低的 SRU。
- time-first/load: 优先选择估计完成时间较短或负载较低的 SRU。
- cross-gain-first: 允许跨链时，优先选择能明显缩短时间的跨链 SRU。
"""

from smdfjsp.core.encoding import op_from_ua_os, random_os
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import RNGPack
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.data.mvc_io import get_candidate_srus, get_intra_chain_srus
from smdfjsp.model.mvc_repair import best_machine_ms, build_random_mvc_individual, repair_mvc_individual


def _strategy_alias(strategy: str) -> str:
    """兼容旧实验脚本里的策略简称。"""

    aliases = {
        "intra": "intra-chain-first",
        "cost": "cost-first",
        "time": "time-first",
        "load": "time-first",
        "cross_gain": "cross-gain-first",
    }
    return aliases.get(strategy, strategy)


def _job_sru_estimates(instance: MVCSMDFJSPInstance, job_id: int, sru_id: int) -> tuple[float, float]:
    """估计某个工件分配到某个 SRU 后的时间和成本。

    这里只做快速估计：每道工序选该 SRU 上最快/最低成本机器，
    再加上该工件到该 SRU 的运输时间、运输成本和跨链固定成本。
    精确目标值仍由 `mvc_evaluator` 在评价阶段计算。
    """

    job = instance.job_map()[job_id]
    proc_time = 0.0
    proc_cost = 0.0
    for op in job.operations:
        options = [opt for opt in op.options if opt.sru_id == sru_id]
        if not options:
            continue
        proc_time += min(float(opt.process_time) for opt in options)
        proc_cost += min(float(opt.process_time) * float(opt.process_cost_per_time) for opt in options)
    key = (job_id, sru_id)
    completion = proc_time + float(instance.transport_time.get(key, 0.0))
    total_cost = (
        proc_cost
        + float(instance.transport_cost.get(key, 0.0))
        + float(instance.cross_chain_fixed_cost.get(key, 0.0))
    )
    return completion, total_cost


def build_heuristic_individual(
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    strategy: str,
) -> EncodedIndividual:
    """按指定启发式策略构造一个可行个体。

    构造顺序：
    1. 根据策略确定 UA，即每个工件分配到哪个 SRU。
    2. 随机生成 OS，保留初始种群的排序多样性。
    3. 由 UA + OS 派生 OP。
    4. 按时间或成本启发式选择 MS。
    5. 最后修复为满足 MVC 约束的可行个体。
    """

    strategy = _strategy_alias(strategy)
    if strategy == "random":
        # 完全随机个体用于防止初始种群被启发式规则限制得过窄。
        ind = build_random_mvc_individual(instance, mode, rng)
        ind.aux["init_strategy"] = strategy
        return ind
    ua = {}
    # `current_load` 只用于 load/time-first 类策略的轻量负载估计。
    current_load = {s.sru_id: 0.0 for s in instance.srus}
    for job in instance.jobs:
        # 候选 SRU 已根据 mode 过滤，例如是否允许跨链。
        candidates = get_candidate_srus(job, instance, mode)
        if strategy == "intra-chain-first":
            # 链内优先策略：只要本价值链内有可加工 SRU，就不主动跨链。
            intra = get_intra_chain_srus(job, instance)
            if intra:
                candidates = intra
        if strategy == "time-first":
            # 时间优先：选择估计完成时间最小的 SRU。
            sid = min(candidates, key=lambda s: _job_sru_estimates(instance, job.job_id, s)[0])
        elif strategy == "cost-first":
            # 成本优先：选择加工、运输、跨链固定成本合计最低的 SRU。
            sid = min(
                candidates,
                key=lambda s: _job_sru_estimates(instance, job.job_id, s)[1],
            )
        elif strategy == "cross-gain-first" and mode.cross_chain_allowed:
            # 跨链收益优先：只在跨链能相对链内最好方案带来时间收益时偏向跨链。
            intra = get_intra_chain_srus(job, instance)
            intra_best = min((_job_sru_estimates(instance, job.job_id, s)[0] for s in intra), default=None)
            cross_candidates = [s for s in candidates if s not in set(intra)]
            if intra_best is not None and cross_candidates:
                sid = max(
                    cross_candidates,
                    key=lambda s: (
                        max(0.0, intra_best - _job_sru_estimates(instance, job.job_id, s)[0]),
                        -_job_sru_estimates(instance, job.job_id, s)[1],
                    ),
                )
            else:
                sid = min(candidates, key=lambda s: _job_sru_estimates(instance, job.job_id, s)[0])
        elif strategy == "load":
            # 负载优先：把工件放到当前估计负载最小的候选 SRU。
            sid = min(candidates, key=lambda s: current_load.get(s, 0.0))
        else:
            sid = int(rng.py_rng.choice(candidates))
        ua[job.job_id] = int(sid)
        # 更新粗略负载，供后续工件分配参考。
        current_load[int(sid)] += sum(min(opt.process_time for opt in op.options if opt.sru_id == sid) for op in job.operations)
    # 初始化阶段只固定 UA 的启发式偏好，OS 保持随机以增加工序顺序多样性。
    os_layer = random_os(instance, rng)  # type: ignore[arg-type]
    op_layer = op_from_ua_os(instance, ua, os_layer)  # type: ignore[arg-type]
    # 时间相关策略用最快机器，成本相关策略用最低成本机器。
    ms_key = "time" if strategy in {"time-first", "cross-gain-first", "load"} else "cost"
    ms_layer = best_machine_ms(instance, op_layer, ms_key)
    ind = repair_mvc_individual(EncodedIndividual(ua=ua, os=os_layer, op=op_layer, ms=ms_layer), instance, mode, rng)
    ind.aux["init_strategy"] = strategy
    return ind
