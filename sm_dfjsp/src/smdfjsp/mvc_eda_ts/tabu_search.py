from __future__ import annotations

"""MVC-EDA-TS 的局部搜索与邻域结构。

主算法负责全局采样，局部搜索负责围绕优秀解做小范围强化。
本文件定义了 6 类邻域：
- N1: 链内 SRU 替换，微调同价值链内部负载。
- N2: 跨链 SRU 替换，主动探索跨价值链协同。
- N3: 跨链回流，把已经跨链的工件迁回本链。
- N4: 关键工件跨链迁移，针对完工时间瓶颈。
- N5: 高成本跨链回流/低成本替换，针对成本瓶颈。
- N6: 机器替换或 OS 插入，做局部机器和排序微调。

局部搜索采用轻量禁忌表避免短周期往返，并统计各邻域贡献，
供主算法自适应调整下一代的邻域采样概率。
"""

import time
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from smdfjsp.core.encoding import build_option_index, op_from_ua_os
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import RNGPack
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.data.mvc_io import get_cross_chain_srus, get_intra_chain_srus
from smdfjsp.metrics.multiobjective import crowding_distance, dominates, fast_non_dominated_sort, merge_non_dominated
from smdfjsp.model.mvc_evaluator import evaluate_mvc_individual
from smdfjsp.model.mvc_repair import best_machine_ms, repair_mvc_individual


NEIGHBORHOOD_KINDS = [
    # 每个字符串既是邻域名称，也是统计字典和 move_kind 里的键。
    "N1_intra_sru_replace",
    "N2_cross_sru_replace",
    "N3_cross_return",
    "N4_critical_cross_migration",
    "N5_high_cost_return",
    "N6_machine_or_os_local",
]


@dataclass
class NeighborhoodStats:
    """记录一次或多次局部搜索中各邻域的贡献。"""

    # generated: 该邻域生成并被评价的候选数量。
    generated: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in NEIGHBORHOOD_KINDS})
    # accepted: 该邻域候选被选为下一步 current 的次数。
    accepted: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in NEIGHBORHOOD_KINDS})
    # archive_inserted: 该邻域候选进入局部非支配档案的次数。
    archive_inserted: Dict[str, int] = field(default_factory=lambda: {k: 0 for k in NEIGHBORHOOD_KINDS})
    # improvement: 该邻域带来的目标值下降量累计，两个目标都按越小越好处理。
    improvement: Dict[str, float] = field(default_factory=lambda: {k: 0.0 for k in NEIGHBORHOOD_KINDS})
    # evaluations: 本次局部搜索消耗的评价次数，用于全局预算控制。
    evaluations: int = 0


def _rank_by_front_and_crowding(objs: List[Tuple[float, ...]]) -> List[int]:
    """按 Pareto 层级和拥挤距离给候选排序。

    返回的是索引序列：非支配层越靠前越优先；同一层中拥挤距离越大越优先，
    表示该解位于更稀疏区域，更有助于保持 Pareto 前沿多样性。
    """

    ranked: List[int] = []
    for front in fast_non_dominated_sort(objs):
        distances = crowding_distance(objs, front)
        ranked.extend(i for i, _ in sorted(zip(front, distances), key=lambda x: x[1], reverse=True))
    return ranked


def _new_sru_neighbor(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    job_id: int,
    to_sru: int,
    move_kind: str,
    extra_aux: Dict[str, object] | None = None,
) -> EncodedIndividual:
    """创建一个“把某工件迁移到新 SRU”的邻域个体。

    SRU 改变会影响 OP 队列和机器可选集合，因此需要：
    1. 修改 UA。
    2. 重新由 UA + OS 生成 OP。
    3. 用时间优先机器选择快速重建 MS。
    4. 写入 move_kind 等 aux 信息，供禁忌表和统计使用。
    5. 调用 repair 保证 MVC 约束合法。
    """

    moved = deepcopy(ind)
    current = moved.ua.get(job_id)
    moved.ua[job_id] = int(to_sru)
    moved.op = op_from_ua_os(instance, moved.ua, moved.os)  # type: ignore[arg-type]
    moved.ms = best_machine_ms(instance, moved.op, "time")
    moved.aux.update(
        {
            "move_kind": move_kind,
            "job_id": int(job_id),
            "from_sru": int(current) if current is not None else -1,
            "to_sru": int(to_sru),
        }
    )
    if extra_aux:
        moved.aux.update(extra_aux)
    # SRU 迁移后，原 MS 中的机器可能不再属于新 SRU，因此必须 repair。
    # repair 只修正编码可行性，不改变该邻域“迁移到 to_sru”的意图。
    return repair_mvc_individual(moved, instance, mode, rng)


def _sample_jobs(instance: MVCSMDFJSPInstance, rng: RNGPack, limit: int = 8):
    """随机抽取一小批工件作为邻域生成对象，控制局部搜索规模。"""

    jobs = list(instance.jobs)
    rng.py_rng.shuffle(jobs)
    return jobs[: min(limit, len(jobs))]


def _n1_intra_sru_replace(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int,
) -> List[EncodedIndividual]:
    """N1: 链内 SRU 替换。

    在同一价值链内给工件换一个可加工 SRU，主要用于释放链内局部拥塞，
    不引入跨链固定成本，属于较稳健的局部调整。
    """

    neighbors: List[EncodedIndividual] = []
    for job in _sample_jobs(instance, rng):
        current = ind.ua.get(job.job_id)
        # N1 只在同价值链内换 SRU，因此不会新增跨链固定成本。
        choices = [sid for sid in get_intra_chain_srus(job, instance) if sid != current]
        if not choices:
            continue
        neighbors.append(
            _new_sru_neighbor(ind, instance, mode, rng, job.job_id, int(rng.py_rng.choice(choices)), "N1_intra_sru_replace")
        )
        if len(neighbors) >= max_neighbors:
            break
    return neighbors


def _n2_cross_sru_replace(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int,
) -> List[EncodedIndividual]:
    """N2: 跨链 SRU 替换。

    把工件迁移到其他价值链的 SRU，可能缩短加工/运输时间，
    但也可能增加跨链成本，因此只在 mode 允许跨链时启用。
    """

    if not mode.cross_chain_allowed:
        return []
    neighbors: List[EncodedIndividual] = []
    for job in _sample_jobs(instance, rng):
        current = ind.ua.get(job.job_id)
        # N2 只看外链同类型 SRU，用于主动探索跨价值链协同带来的时间或负载改善。
        choices = [sid for sid in get_cross_chain_srus(job, instance) if sid != current]
        if not choices:
            continue
        neighbors.append(
            _new_sru_neighbor(ind, instance, mode, rng, job.job_id, int(rng.py_rng.choice(choices)), "N2_cross_sru_replace")
        )
        if len(neighbors) >= max_neighbors:
            break
    return neighbors


def _n3_cross_return(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int,
) -> List[EncodedIndividual]:
    """N3: 跨链回流。

    找出当前已经被分配到外链 SRU 的工件，尝试迁回本价值链内 SRU。
    该邻域主要用于纠正不划算的跨链分配。
    """

    sru_map = instance.sru_map()
    neighbors: List[EncodedIndividual] = []
    cross_jobs = [
        job
        for job in instance.jobs
        if ind.ua.get(job.job_id) in sru_map and sru_map[ind.ua[job.job_id]].value_chain_id != job.value_chain_id
    ]
    rng.py_rng.shuffle(cross_jobs)
    for job in cross_jobs:
        current = ind.ua.get(job.job_id)
        # N3 的目标是“回本链”，因此候选只取链内 SRU。
        choices = [sid for sid in get_intra_chain_srus(job, instance) if sid != current]
        if not choices:
            continue
        neighbors.append(
            _new_sru_neighbor(ind, instance, mode, rng, job.job_id, int(rng.py_rng.choice(choices)), "N3_cross_return")
        )
        if len(neighbors) >= max_neighbors:
            break
    return neighbors


def _critical_jobs(ind: EncodedIndividual, instance: MVCSMDFJSPInstance, mode: MVCModeConfig) -> List[int]:
    """识别当前解中最可能影响 makespan 的关键工件。

    使用评价记录得到每个工件的最后完工时间，再加运输时间粗略排序，
    返回排在最前的少数工件，供 N4 做有针对性的跨链迁移。
    """

    ev = ind.aux.get("mvc_eval")
    if ev is None:
        ev = evaluate_mvc_individual(instance, ind, mode)
        ind.aux["mvc_eval"] = ev
    completion = {job.job_id: 0.0 for job in instance.jobs}
    for rec in ev.records:
        completion[rec.job_id] = max(completion.get(rec.job_id, 0.0), float(rec.end))
    scored = []
    for job_id, ctime in completion.items():
        sid = ind.ua.get(job_id)
        if sid is None:
            continue
        # 关键性按“加工完工 + 运输时间”估计，与评价器中的 makespan 定义保持一致。
        scored.append((ctime + float(instance.transport_time.get((job_id, sid), 0.0)), job_id))
    return [job_id for _, job_id in sorted(scored, reverse=True)[:3]]


def _n4_critical_cross_migration(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int,
) -> List[EncodedIndividual]:
    """N4: 关键工件跨链迁移。

    对完工时间靠后的关键工件，选择估计完成时间最短的外链 SRU。
    这是面向 makespan 瓶颈的主动跨链搜索。
    """

    if not mode.cross_chain_allowed:
        return []
    option_index = build_option_index(instance)  # type: ignore[arg-type]
    neighbors: List[EncodedIndividual] = []
    for job_id in _critical_jobs(ind, instance, mode):
        job = instance.job_map()[job_id]
        current = ind.ua.get(job_id)
        choices = [sid for sid in get_cross_chain_srus(job, instance) if sid != current]
        if not choices:
            continue

        def estimate(sid: int) -> float:
            """估计迁移到某个 SRU 后的加工+运输时间。"""

            total = float(instance.transport_time.get((job_id, sid), 0.0))
            for op in job.operations:
                options = option_index.get((job_id, op.op_id, sid), {})
                if options:
                    # N4 是 makespan 导向邻域，所以这里用最短加工时间近似该 SRU 的速度。
                    total += min(float(pt) for pt, _ in options.values())
            return total

        to_sru = min(choices, key=estimate)
        neighbors.append(
            _new_sru_neighbor(
                ind,
                instance,
                mode,
                rng,
                job_id,
                int(to_sru),
                "N4_critical_cross_migration",
                {"critical_ranked": True},
            )
        )
        if len(neighbors) >= max_neighbors:
            break
    return neighbors


def _n5_high_cost_return(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int,
) -> List[EncodedIndividual]:
    """N5: 高成本跨链回流/替换。

    先找出跨链固定成本和运输成本最高的跨链工件，
    再尝试迁回链内或选择成本更低的跨链 SRU，主要优化成本目标。
    """

    sru_map = instance.sru_map()
    scored = []
    for job in instance.jobs:
        sid = ind.ua.get(job.job_id)
        if sid not in sru_map or sru_map[sid].value_chain_id == job.value_chain_id:
            continue
        key = (job.job_id, sid)
        cost = float(instance.transport_cost.get(key, 0.0)) + float(instance.cross_chain_fixed_cost.get(key, 0.0))
        scored.append((cost, job))
    neighbors: List[EncodedIndividual] = []
    for _, job in sorted(scored, key=lambda x: (x[0], x[1].job_id), reverse=True)[: max_neighbors]:
        current = ind.ua.get(job.job_id)
        choices = [sid for sid in get_intra_chain_srus(job, instance) if sid != current]
        if mode.cross_chain_allowed:
            cross_choices = [sid for sid in get_cross_chain_srus(job, instance) if sid != current]
            if cross_choices:
                # 除了回本链，N5 也允许换到成本更低的外链 SRU，避免过度保守。
                cheapest_cross = min(
                    cross_choices,
                    key=lambda sid: float(instance.transport_cost.get((job.job_id, sid), 0.0))
                    + float(instance.cross_chain_fixed_cost.get((job.job_id, sid), 0.0)),
                )
                choices.append(int(cheapest_cross))
        if not choices:
            continue
        to_sru = min(
            set(choices),
            key=lambda sid: float(instance.transport_cost.get((job.job_id, sid), 0.0))
            + float(instance.cross_chain_fixed_cost.get((job.job_id, sid), 0.0)),
        )
        neighbors.append(_new_sru_neighbor(ind, instance, mode, rng, job.job_id, int(to_sru), "N5_high_cost_return"))
        if len(neighbors) >= max_neighbors:
            break
    return neighbors


def _n6_machine_or_os_local(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int,
) -> List[EncodedIndividual]:
    """N6: 机器替换或 OS 插入。

    该邻域不改变工件所属 SRU，而是在固定分配下微调：
    - OS insert: 改变同类型 OS 中一个工件 token 的位置，影响工序排序。
    - machine_replace: 给某道工序换另一台可加工机器。
    """

    option_index = build_option_index(instance)  # type: ignore[arg-type]
    neighbors: List[EncodedIndividual] = []
    for type_id, vec in ind.os.items():
        # OS 插入移动：从一个位置取出 token，再插入到另一个位置。
        # OS 改变的是同服务类型订单的相对加工顺序，不改变任何订单的 SRU 归属。
        if len(vec) < 2 or len(neighbors) >= max_neighbors:
            continue
        from_pos = rng.py_rng.randrange(len(vec))
        to_pos = rng.py_rng.randrange(len(vec))
        if from_pos != to_pos:
            new_vec = list(vec)
            token = new_vec.pop(from_pos)
            new_vec.insert(to_pos, token)
            moved = EncodedIndividual(
                ua=dict(ind.ua),
                os={k: (new_vec if k == type_id else list(v)) for k, v in ind.os.items()},
                op={},
                ms={},
                aux={
                    "move_kind": "N6_machine_or_os_local",
                    "local_move": "os_insert",
                    "type_id": int(type_id),
                    "job_id": int(token),
                    "from_pos": int(from_pos),
                    "to_pos": int(to_pos),
                },
            )
            moved.op = op_from_ua_os(instance, moved.ua, moved.os)  # type: ignore[arg-type]
            moved.ms = best_machine_ms(instance, moved.op, "time")
            neighbors.append(repair_mvc_individual(moved, instance, mode, rng))

    for sru_id, seq in ind.op.items():
        # 机器替换移动：在同一 SRU 的同一道工序上换一台候选机器。
        # 它只微调 MS 层，适合在 UA/OS 已经较好时继续压缩时间或成本。
        if not seq or len(neighbors) >= max_neighbors:
            continue
        pos = rng.py_rng.randrange(len(seq))
        job_id, op_id = seq[pos]
        choices = list(option_index[(job_id, op_id, sru_id)])
        current = ind.ms.get(sru_id, [])[pos] if pos < len(ind.ms.get(sru_id, [])) else None
        choices = [m for m in choices if m != current]
        if not choices:
            continue
        moved = deepcopy(ind)
        moved.ms[sru_id][pos] = int(rng.py_rng.choice(choices))
        moved.aux.update(
            {
                "move_kind": "N6_machine_or_os_local",
                "local_move": "machine_replace",
                "sru_id": int(sru_id),
                "job_id": int(job_id),
                "op_id": int(op_id),
                "position": int(pos),
            }
        )
        neighbors.append(repair_mvc_individual(moved, instance, mode, rng))
    return neighbors[:max_neighbors]


_NEIGHBOR_FUNCS = {
    # 邻域名称到生成函数的映射，便于按开关/概率统一调度。
    "N1_intra_sru_replace": _n1_intra_sru_replace,
    "N2_cross_sru_replace": _n2_cross_sru_replace,
    "N3_cross_return": _n3_cross_return,
    "N4_critical_cross_migration": _n4_critical_cross_migration,
    "N5_high_cost_return": _n5_high_cost_return,
    "N6_machine_or_os_local": _n6_machine_or_os_local,
}


def generate_mvc_neighbors(
    ind: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    max_neighbors: int = 60,
    enabled_kinds: List[str] | None = None,
    probabilities: Dict[str, float] | None = None,
) -> List[EncodedIndividual]:
    """按启用邻域和概率生成一批候选邻居。

    `probabilities` 来自主算法的自适应邻域权重。
    每类邻域按权重分配生成配额，最后打乱并截断到 `max_neighbors`。
    """

    kinds = [k for k in (enabled_kinds or NEIGHBORHOOD_KINDS) if k in _NEIGHBOR_FUNCS]
    if not kinds:
        return []
    weights = [max(float((probabilities or {}).get(k, 1.0)), 0.0) for k in kinds]
    if sum(weights) <= 0.0:
        weights = [1.0 for _ in kinds]
    total_weight = sum(weights)
    neighbors: List[EncodedIndividual] = []
    for kind, weight in zip(kinds, weights):
        # 按权重给每种邻域分配候选数量，至少生成 1 个避免被完全饿死。
        quota = max(1, int(round(max_neighbors * weight / total_weight)))
        # 具体邻域函数内部仍可能因为没有合法候选而返回空列表。
        neighbors.extend(_NEIGHBOR_FUNCS[kind](ind, instance, mode, rng, quota))
    rng.py_rng.shuffle(neighbors)
    return neighbors[:max_neighbors]


def _tabu_key(ind: EncodedIndividual) -> Tuple[object, ...] | None:
    """把一个移动编码成禁忌表 key。

    目前对 SRU 迁移和 OS 插入建立禁忌，防止短时间内反复做相反或同类移动。
    机器替换没有纳入禁忌表，因为机器微调搜索空间小，过强禁忌可能抑制改进。
    """

    mk = str(ind.aux.get("move_kind", ""))
    if mk in {"N1_intra_sru_replace", "N2_cross_sru_replace", "N3_cross_return", "N4_critical_cross_migration", "N5_high_cost_return"}:
        # SRU 迁移类 key 记录“哪个订单从哪到哪”，防止近期反复迁移同一个订单。
        return (
            mk,
            int(ind.aux["job_id"]),
            int(ind.aux["from_sru"]),
            int(ind.aux["to_sru"]),
        )
    if mk == "N6_machine_or_os_local" and ind.aux.get("local_move") == "os_insert":
        # OS 插入类 key 记录 token 和位置变化，防止短周期内撤销/重复同一排序移动。
        return (
            mk,
            "os_insert",
            int(ind.aux["type_id"]),
            int(ind.aux["job_id"]),
            int(ind.aux["from_pos"]),
            int(ind.aux["to_pos"]),
        )
    return None


def _enabled_kinds(
    use_cross_chain_neighbors: bool,
    use_critical_migration: bool,
    use_cost_return: bool,
) -> List[str]:
    """根据消融开关决定本次局部搜索可用的邻域集合。"""

    kinds = ["N1_intra_sru_replace", "N6_machine_or_os_local"]
    # N1/N6 是基础局部微调；跨链相关 N2-N5 由消融开关统一控制。
    if use_cross_chain_neighbors:
        kinds.extend(["N2_cross_sru_replace", "N3_cross_return"])
        if use_critical_migration:
            kinds.append("N4_critical_cross_migration")
        if use_cost_return:
            kinds.append("N5_high_cost_return")
    return kinds


def local_search(
    seed: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
    steps: int,
    neighborhood_probabilities: Dict[str, float] | None = None,
    use_cross_chain_neighbors: bool = True,
    use_critical_migration: bool = True,
    use_cost_return: bool = True,
    max_evaluations: int | None = None,
    deadline_s: float | None = None,
    time_measure: str = "wall",
    return_stats: bool = False,
) -> EncodedIndividual | Tuple[EncodedIndividual, NeighborhoodStats]:
    """从一个种子解出发执行局部搜索。

    搜索逻辑：
    1. 评价种子解并初始化局部非支配档案。
    2. 每一步按启用邻域生成候选并评价。
    3. 用局部非支配排序和拥挤距离选候选。
    4. 用禁忌表过滤近期移动；若候选支配历史 best，则触发 aspiration 允许破禁。
    5. 更新 current、best、局部档案和邻域统计。

    返回值默认是搜索得到的个体；`return_stats=True` 时同时返回邻域统计。
    """

    if time_measure not in {"wall", "cpu"}:
        raise ValueError("time_measure must be 'wall' or 'cpu'")
    clock = time.process_time if time_measure == "cpu" else time.perf_counter
    best = seed
    stats = NeighborhoodStats()
    # 如果种子已经在主流程中评价过，会把评价结果缓存在 aux["mvc_eval"] 中。
    best_eval = best.aux.get("mvc_eval")
    if best_eval is None:
        if (max_evaluations is not None and max_evaluations <= 0) or (
            deadline_s is not None and clock() >= deadline_s
        ):
            return (best, stats) if return_stats else best
        best_eval = evaluate_mvc_individual(instance, best, mode)
        best.aux["mvc_eval"] = best_eval
        stats.evaluations += 1
    best.objectives = best_eval.objectives  # type: ignore[assignment]
    best.feasible = best_eval.feasible
    current = best
    local_nd: List[Tuple[Tuple[float, ...], EncodedIndividual]] = []
    if best.objectives is not None:
        local_nd = merge_non_dominated([], [(tuple(best.objectives), best)])
    tabu_list: List[Tuple[object, ...]] = []
    # 禁忌表长度与 OS 规模相关，规模越大允许保留更多近期移动。
    tabu_max_len = max(1, sum(min(5, len(v)) for v in seed.os.values()))
    enabled = _enabled_kinds(use_cross_chain_neighbors, use_critical_migration, use_cost_return)

    for _ in range(max(0, steps)):
        # 时间预算和评价次数预算在每一步都检查，保证不会明显越界。
        if deadline_s is not None and clock() >= deadline_s:
            break
        remaining = None if max_evaluations is None else max_evaluations - stats.evaluations
        if remaining is not None and remaining <= 0:
            break
        before_nd = len(local_nd)
        # 生成邻居时已按自适应概率分配各邻域数量。
        neighbors = generate_mvc_neighbors(
            current,
            instance,
            mode,
            rng,
            enabled_kinds=enabled,
            probabilities=neighborhood_probabilities,
            max_neighbors=min(60, remaining) if remaining is not None else 60,
        )
        if not neighbors:
            break
        evaluated_neighbors: List[EncodedIndividual] = []
        for nb in neighbors:
            if deadline_s is not None and clock() >= deadline_s:
                break
            if max_evaluations is not None and stats.evaluations >= max_evaluations:
                break
            mk = str(nb.aux.get("move_kind", ""))
            if mk in stats.generated:
                stats.generated[mk] += 1
            ev = evaluate_mvc_individual(instance, nb, mode)
            # 缓存评价结果，避免后续关键工件识别或其他逻辑重复评价。
            nb.aux["mvc_eval"] = ev
            stats.evaluations += 1
            nb.objectives = ev.objectives  # type: ignore[assignment]
            nb.feasible = ev.feasible
            evaluated_neighbors.append(nb)
        feasible_neighbors = [nb for nb in evaluated_neighbors if nb.feasible and nb.objectives is not None]
        if not feasible_neighbors:
            break
        # 局部档案保存本次 TS 已见到的非支配候选；即使某个候选没有成为 current，
        # 只要它对 Pareto 前沿有贡献，最终仍可能被返回。
        # 更新局部非支配档案，并统计哪些邻域真正贡献了新的非支配解。
        local_nd = merge_non_dominated(
            local_nd,
            [(tuple(nb.objectives), nb) for nb in feasible_neighbors if nb.objectives is not None],
        )
        if len(local_nd) > before_nd:
            for _, nd_ind in local_nd[before_nd:]:
                mk = str(nd_ind.aux.get("move_kind", ""))
                if mk in stats.archive_inserted:
                    stats.archive_inserted[mk] += 1

        # 候选排序先看 Pareto 层级，再看拥挤距离。
        ranked = _rank_by_front_and_crowding([tuple(nb.objectives or ()) for nb in feasible_neighbors])
        candidate = feasible_neighbors[ranked[0]]
        for idx in ranked:
            nb = feasible_neighbors[idx]
            key = _tabu_key(nb)
            # Aspiration：即使移动在禁忌表里，只要能支配当前 best，也允许接受。
            improves_best = best.objectives is not None and nb.objectives is not None and dominates(nb.objectives, best.objectives)
            if key is None or key not in tabu_list or improves_best:
                candidate = nb
                if key is not None:
                    if key in tabu_list:
                        tabu_list.remove(key)
                    tabu_list.append(key)
                    if len(tabu_list) > tabu_max_len:
                        tabu_list.pop(0)
                break

        chosen_kind = str(candidate.aux.get("move_kind", ""))
        if chosen_kind in stats.accepted:
            stats.accepted[chosen_kind] += 1
        old_obj = tuple(current.objectives or ())
        # TS 采用“移动到排序最佳的允许候选”的策略，因此 current 可以不是历史 best。
        # 这有助于跳出局部结构，best/local_nd 则负责保留真正优秀的解。
        current = candidate
        if candidate.objectives is not None and old_obj:
            # 改善量按所有目标的正向下降量求和，只记录越小越好的改进。
            gain = sum(max(0.0, float(old_obj[i]) - float(candidate.objectives[i])) for i in range(len(candidate.objectives)))
            if chosen_kind in stats.improvement:
                stats.improvement[chosen_kind] += gain
        if candidate.objectives is not None and best.objectives is not None and dominates(candidate.objectives, best.objectives):
            best = candidate

    result = best
    if local_nd:
        # 多目标场景下局部搜索最终返回局部非支配档案中排序最靠前的解。
        ranked_nd = _rank_by_front_and_crowding([x[0] for x in local_nd])
        result = local_nd[ranked_nd[0]][1]
    if return_stats:
        return result, stats
    return result
