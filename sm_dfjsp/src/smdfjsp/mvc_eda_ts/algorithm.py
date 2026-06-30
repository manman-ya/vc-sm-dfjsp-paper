from __future__ import annotations

"""MVC-EDA-TS 主算法流程。

这个文件负责把各个子模块串起来：
- `MVCProbabilityModel` 维护 EDA 的三类概率模型，用来采样 UA/OS/MS 三层编码。
- `build_heuristic_individual` 负责生成带价值链偏好的初始种群。
- `local_search` 负责基于多种邻域的禁忌/局部搜索强化。
- `NonDominatedArchive` 负责保存当前发现的非支配解，作为学习和输出记忆。

编码含义：
- UA: unit assignment，工件分配到哪个 SRU。
- OS: operation sequence，按类型分层的工序顺序编码。
- OP: operation processing list，由 UA 和 OS 派生出的每个 SRU 上的工序队列。
- MS: machine selection，每个 OP 位置选择哪台机器加工。
"""

import time
from dataclasses import dataclass
from typing import Dict, List

from smdfjsp.core.encoding import build_option_index, op_from_ua_os
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import make_rng
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.metrics.multiobjective import crowding_distance, fast_non_dominated_sort
from smdfjsp.model.mvc_evaluator import evaluate_mvc_population
from smdfjsp.model.mvc_repair import repair_mvc_individual
from smdfjsp.mvc_eda_ts.archive import NonDominatedArchive
from smdfjsp.mvc_eda_ts.initialization import build_heuristic_individual
from smdfjsp.mvc_eda_ts.probability_model import MVCProbabilityModel
from smdfjsp.mvc_eda_ts.tabu_search import NEIGHBORHOOD_KINDS, NeighborhoodStats, local_search


@dataclass
class MVCEDATSConfig:
    """MVC-EDA-TS 的所有控制参数。

    前半部分是通用进化参数，后半部分是论文机制/消融开关。
    消融实验通过关闭这些布尔开关来验证模块贡献。
    """

    popsize: int = 50
    # 最大迭代代数；实际运行还会受到 `time_limit_s` 和 `max_evaluations` 限制。
    max_iter: int = 100
    # 单次运行时间预算，含初始化、采样、局部搜索和选择。
    time_limit_s: float = 100.0
    # UA 概率模型学习率：越大越快靠近精英解的 SRU 分配频率。
    alpha: float = 0.5
    # OS 概率模型学习率：越大越快靠近精英解的工序位置分布。
    beta: float = 0.5
    # MS 概率模型学习率：越大越快靠近精英解的机器选择频率。
    gamma: float = 0.5
    # 每代参与概率模型更新的精英比例。
    mu: float = 0.1
    # 兼容旧版 EDA-TS 的惩罚参数；当前 MVC 局部搜索主要用邻域奖励统计。
    epsilon: float = 0.008
    # 每代最多挑选多少个解作为局部搜索起点。
    tmax: int = 10
    # 初始化时启发式种群的比例参数，当前保留给兼容/实验记录。
    elite_ratio: float = 0.2
    # 每个局部搜索起点向前搜索的步数。
    local_search_steps: int = 8
    # 非支配档案最大容量，过大保留多样性但增加排序成本。
    nd_pool_max: int = 300
    # 可选的评价次数预算，用于公平比较不同算法。
    max_evaluations: int | None = None
    # 计时口径：wall 使用真实经过时间，cpu 使用进程 CPU 时间。
    time_measure: str = "wall"
    seed: int = 42
    # 是否使用价值链启发式初始化；关闭时退化为随机/模型采样。
    use_value_chain_init: bool = True
    # 是否把价值链成本/时间先验注入 UA 概率模型。
    use_value_chain_prior: bool = True
    prior_weight: float = 0.35
    # 是否使用 EDA 概率模型；关闭时主要依赖随机启发式个体。
    use_probability_model: bool = True
    # 以下开关控制 MVC 论文机制中的跨链邻域和自适应机制。
    use_cross_chain_neighbors: bool = True
    use_bottleneck_release: bool = True
    use_critical_migration: bool = True
    use_cost_return: bool = True
    use_adaptive_neighborhood: bool = True
    use_nd_memory: bool = True


@dataclass
class MVCEDATSResult:
    """算法运行结果。

    `nd_solutions` 是最终非支配解集；`history` 记录每代最优目标、
    档案大小、评价次数和各模块累计耗时，用于复现实验和画收敛曲线。
    """

    nd_solutions: List[EncodedIndividual]
    history: List[Dict[str, float]]
    stop_reason: str = ""
    iterations_completed: int = 0
    elapsed_s: float = 0.0
    evaluation_count: int = 0
    module_runtime_s: Dict[str, float] | None = None
    budget_elapsed_s: float = 0.0
    time_measure: str = "wall"

    @property
    def evaluations_completed(self) -> int:
        return self.evaluation_count

    @property
    def phase_times(self) -> Dict[str, float] | None:
        return self.module_runtime_s


class MVCEDATS:
    """多价值链共享制造场景下的 EDA-TS 求解器。"""

    def __init__(
        self,
        instance: MVCSMDFJSPInstance,
        config: MVCEDATSConfig,
        mode: MVCModeConfig | None = None,
    ):
        self.instance = instance
        self.cfg = config
        self.mode = mode or MVCModeConfig()
        self.rng = make_rng(config.seed)
        # 概率模型是 EDA 的核心：后续每代都从精英解/档案学习，再采样新解。
        self.model = MVCProbabilityModel(
            instance,
            self.mode,
            smoothing=0.25,
            use_value_chain_prior=config.use_value_chain_prior,
            prior_weight=config.prior_weight,
        )
        # `option_index[(job, op, sru)] -> {machine: (processing_time, cost_rate)}`
        # 用于机器选择启发式和局部搜索修复。
        self.option_index = build_option_index(instance)  # type: ignore[arg-type]
        # 各邻域初始均匀分配搜索预算，后续按实际贡献自适应调整。
        # 这里的概率只影响局部搜索阶段生成不同邻域候选的配额，不影响 EDA 采样本身。
        self.neighborhood_probabilities: Dict[str, float] = {
            kind: 1.0 / len(NEIGHBORHOOD_KINDS) for kind in NEIGHBORHOOD_KINDS
        }

    def _select_elite(self, pop: List[EncodedIndividual], elite_size: int | None = None) -> List[EncodedIndividual]:
        """按 Pareto 等级和拥挤距离选择精英。

        先优先选择更靠前的非支配层；如果某一层不能全部放入，
        用拥挤距离保留分布更稀疏的个体，避免概率模型过早收敛。
        """

        if elite_size is None:
            elite_size = max(1, int(self.cfg.mu * self.cfg.popsize))
        objs = [tuple(ind.objectives or ()) for ind in pop]
        fronts = fast_non_dominated_sort(objs)
        selected: List[EncodedIndividual] = []
        for front in fronts:
            if len(selected) + len(front) <= elite_size:
                selected.extend(pop[i] for i in front)
            else:
                dist = crowding_distance(objs, front)
                ranked = sorted(zip(front, dist), key=lambda x: x[1], reverse=True)
                selected.extend(pop[i] for i, _ in ranked[: elite_size - len(selected)])
                break
        return selected

    def _sample_from_model(self) -> EncodedIndividual:
        """直接从当前概率模型采样一个个体。

        该函数保留为独立入口，便于测试或未来替换采样策略。
        当前 `_build_individual` 会在此基础上加入价值链启发式混合。
        """

        if not self.cfg.use_probability_model:
            return build_heuristic_individual(self.instance, self.mode, self.rng, "random")
        ua = self.model.sample_ua(self.rng)
        os_layer = self.model.sample_os(self.rng)
        op_layer = op_from_ua_os(self.instance, ua, os_layer)  # type: ignore[arg-type]
        ms_layer = self.model.sample_ms(op_layer, self.rng)
        return repair_mvc_individual(EncodedIndividual(ua=ua, os=os_layer, op=op_layer, ms=ms_layer), self.instance, self.mode, self.rng)

    def _md_ua(self) -> Dict[int, int]:
        """构造最小运输时间的 UA 层。

        MD 可以理解为 minimum-distance / minimum-transport-time 分配，
        用少量确定性优质个体提高初始种群和采样种群质量。
        """

        ua: Dict[int, int] = {}
        for job in self.instance.jobs:
            choices = self.model.candidates[job.job_id]
            ua[job.job_id] = min(choices, key=lambda sid: self.instance.transport_time[(job.job_id, sid)])
        return ua

    def _mct_ms(self, op_layer: Dict[int, List[tuple[int, int]]]) -> Dict[int, List[int]]:
        """按最早完工时间贪心生成 MS 层。

        对每个 SRU 队列中的工序，选择使该工序预计完成时间最小的机器。
        这里只是构造初始/采样个体的启发式，不替代完整调度评价器。
        """

        ms: Dict[int, List[int]] = {}
        machine_ready: Dict[tuple[int, int], float] = {}
        job_ready: Dict[int, float] = {job.job_id: 0.0 for job in self.instance.jobs}
        for sru_id, seq in op_layer.items():
            vec: List[int] = []
            for job_id, op_id in seq:
                options = self.option_index[(job_id, op_id, sru_id)]
                best_machine = min(
                    options,
                    key=lambda machine_id: max(job_ready[job_id], machine_ready.get((sru_id, machine_id), 0.0))
                    + options[machine_id][0],
                )
                finish = max(job_ready[job_id], machine_ready.get((sru_id, best_machine), 0.0)) + options[best_machine][0]
                machine_ready[(sru_id, best_machine)] = finish
                job_ready[job_id] = finish
                vec.append(int(best_machine))
            ms[sru_id] = vec
        return ms

    def _build_individual(self) -> EncodedIndividual:
        """生成一个可行编码个体。

        多源生成策略：
        1. UA 层多数来自概率模型，少数来自最小运输时间启发式。
        2. OS 层来自概率模型，表示各类型工件的工序排序偏好。
        3. MS 层混合概率采样、最低成本机器、最早完成机器三种策略。
        4. 最后统一调用 `repair_mvc_individual`，修复跨链/机器兼容性等约束。
        """

        if not self.cfg.use_probability_model:
            return build_heuristic_individual(self.instance, self.mode, self.rng, "random")

        if self.cfg.use_value_chain_init:
            # 大部分 UA 来自概率模型，少量使用最小运输时间 UA。
            # 这样既利用 EDA 学到的分布，也定期注入明确偏向短运输路径的结构化个体。
            ua = self.model.sample_ua(self.rng) if self.rng.py_rng.random() < 0.8 else self._md_ua()
        else:
            ua = self.model.sample_ua(self.rng)
        os_layer = self.model.sample_os(self.rng)
        op_layer = op_from_ua_os(self.instance, ua, os_layer)  # type: ignore[arg-type]
        if self.cfg.use_value_chain_init:
            r = self.rng.py_rng.random()
            if r < 0.6:
                # 主路径：按 PMM 概率采样机器，保留从精英中学习到的机器偏好。
                ms_layer = self.model.sample_ms(op_layer, self.rng)
            elif r < 0.8:
                from smdfjsp.model.mvc_repair import best_machine_ms

                # 成本导向补充路径：让采样种群覆盖低加工成本机器组合。
                ms_layer = best_machine_ms(self.instance, op_layer, "cost")
            else:
                # 时间导向补充路径：用最早完工启发式缓解 makespan 目标。
                ms_layer = self._mct_ms(op_layer)
        else:
            ms_layer = self.model.sample_ms(op_layer, self.rng)
        return repair_mvc_individual(EncodedIndividual(ua=ua, os=os_layer, op=op_layer, ms=ms_layer), self.instance, self.mode, self.rng)

    def _initial_population(self) -> List[EncodedIndividual]:
        """构造初始种群。

        开启价值链初始化时，按多种启发式轮流生成个体，保证初始种群
        同时覆盖随机、链内优先、成本优先、时间优先和跨链收益优先等区域。
        """

        if not self.cfg.use_value_chain_init:
            pop = [self._build_individual() for _ in range(self.cfg.popsize)]
            for ind in pop:
                ind.aux["init_strategy"] = "model-sampling"
            return pop
        strategies = ["random", "intra-chain-first", "cost-first", "time-first"]
        if self.mode.cross_chain_allowed:
            strategies.append("cross-gain-first")
        pop: List[EncodedIndividual] = []
        for idx in range(self.cfg.popsize):
            strategy = strategies[idx % len(strategies)]
            # 轮转策略而非按比例随机抽样，可以保证小种群下每种初始化思想至少出现。
            pop.append(build_heuristic_individual(self.instance, self.mode, self.rng, strategy))
        self.rng.py_rng.shuffle(pop)
        return pop

    def _select_search_seeds(self, candidates: List[EncodedIndividual], count: int) -> List[EncodedIndividual]:
        """选择局部搜索起点。

        与精英选择类似，先按非支配层排序，再按拥挤距离保留稀疏区域的解。
        这样 TS 不只强化单个最优角点，也会探索 Pareto 前沿的不同位置。
        """

        if not candidates or count <= 0:
            return []
        objs = [tuple(ind.objectives or ()) for ind in candidates]
        fronts = fast_non_dominated_sort(objs)
        ordered: List[int] = []
        for front in fronts:
            distances = crowding_distance(objs, front)
            ordered.extend(i for i, _ in sorted(zip(front, distances), key=lambda x: x[1], reverse=True))
        return [candidates[i] for i in ordered[: min(count, len(ordered))]]

    def _update_neighborhood_probabilities(self, stats: NeighborhoodStats) -> Dict[str, float]:
        """根据本代局部搜索统计自适应更新各邻域概率。

        奖励由三部分组成：被接受次数、插入非支配档案次数、目标改善量。
        使用平滑更新而不是直接替换，避免某一代偶然表现导致邻域概率剧烈抖动。
        """

        rewards: Dict[str, float] = {}
        for kind in NEIGHBORHOOD_KINDS:
            rewards[kind] = (
                float(stats.accepted.get(kind, 0))
                + 2.0 * float(stats.archive_inserted.get(kind, 0))
                + 0.01 * float(stats.improvement.get(kind, 0.0))
            )
            # accepted 表示该邻域能推动当前解移动；archive_inserted 表示贡献了新的非支配解；
            # improvement 是目标下降幅度，量纲可能较大，所以只给较小系数。
        total = sum(rewards.values())
        if total <= 0.0:
            target = {kind: 1.0 / len(NEIGHBORHOOD_KINDS) for kind in NEIGHBORHOOD_KINDS}
        else:
            target = {kind: rewards[kind] / total for kind in NEIGHBORHOOD_KINDS}
        rho = 0.25
        for kind in NEIGHBORHOOD_KINDS:
            self.neighborhood_probabilities[kind] = (
                (1.0 - rho) * self.neighborhood_probabilities.get(kind, 1.0 / len(NEIGHBORHOOD_KINDS))
                + rho * target[kind]
            )
        norm = sum(self.neighborhood_probabilities.values())
        if norm > 0.0:
            self.neighborhood_probabilities = {k: v / norm for k, v in self.neighborhood_probabilities.items()}
        return rewards

    @staticmethod
    def _merge_neighborhood_stats(items: List[NeighborhoodStats]) -> NeighborhoodStats:
        """合并多个局部搜索起点产生的邻域统计。"""

        merged = NeighborhoodStats()
        for item in items:
            for kind in NEIGHBORHOOD_KINDS:
                merged.generated[kind] += item.generated.get(kind, 0)
                merged.accepted[kind] += item.accepted.get(kind, 0)
                merged.archive_inserted[kind] += item.archive_inserted.get(kind, 0)
                merged.improvement[kind] += item.improvement.get(kind, 0.0)
        return merged

    def run(self) -> MVCEDATSResult:
        """执行完整 MVC-EDA-TS 主循环。

        每一代包含：
        1. 选择精英并用非支配档案增强学习集。
        2. 更新 UA/OS/MS 概率模型。
        3. 从概率模型和启发式混合采样新种群并评价。
        4. 从档案或精英中挑选起点做局部搜索。
        5. 更新非支配档案，并用 NSGA-II 式环境选择回到固定种群规模。
        """

        if self.cfg.time_measure not in {"wall", "cpu"}:
            raise ValueError("time_measure must be 'wall' or 'cpu'")
        clock = time.process_time if self.cfg.time_measure == "cpu" else time.perf_counter
        wall_start = time.perf_counter()
        budget_start = clock()
        deadline_s = budget_start + self.cfg.time_limit_s
        module_runtime = {
            "initialization": 0.0,
            "probability_update": 0.0,
            "sampling_evaluation": 0.0,
            "local_search": 0.0,
            "archive_selection": 0.0,
        }
        evaluation_count = 0
        phase_start = clock()
        # 初始化阶段：先产生可行初始种群并完成目标函数评价。
        pop = self._initial_population()
        if self.cfg.max_evaluations is not None and self.cfg.max_evaluations < len(pop):
            raise ValueError("max_evaluations must be at least popsize")
        evaluate_mvc_population(self.instance, pop, self.mode)
        evaluation_count += len(pop)
        archive = NonDominatedArchive(max_size=self.cfg.nd_pool_max)
        if self.cfg.use_nd_memory:
            archive.update(pop)
        history: List[Dict[str, float]] = []
        stop_reason = "max_iter"
        module_runtime["initialization"] += clock() - phase_start

        for it in range(1, self.cfg.max_iter + 1):
            # 预算检查放在每代开头，保证时间/评价次数约束优先于迭代次数。
            if clock() >= deadline_s:
                stop_reason = "time_limit"
                break
            if self.cfg.max_evaluations is not None and evaluation_count >= self.cfg.max_evaluations:
                stop_reason = "max_evaluations"
                break
            phase_start = clock()
            elite_size = max(1, int(self.cfg.mu * self.cfg.popsize))
            elites = self._select_elite(pop, elite_size)
            # 学习集 = 当前种群精英 + 历史非支配档案。
            # 这样既学习近期搜索趋势，也保留历史 Pareto 前沿信息。
            learning_set = elites + (archive.solutions() if self.cfg.use_nd_memory else [])
            # 概率模型更新后，下一批 UA/OS/MS 采样会向学习集中的结构靠拢。
            self.model.update(learning_set, alpha=self.cfg.alpha, beta=self.cfg.beta, gamma=self.cfg.gamma)
            module_runtime["probability_update"] += clock() - phase_start

            phase_start = clock()
            # 采样阶段：逐个生成并立即评价，便于严格遵守 max_evaluations。
            remaining = (
                self.cfg.popsize
                if self.cfg.max_evaluations is None
                else min(self.cfg.popsize, self.cfg.max_evaluations - evaluation_count)
            )
            new_pop: List[EncodedIndividual] = []
            for _ in range(max(0, remaining)):
                if clock() >= deadline_s:
                    stop_reason = "time_limit"
                    break
                candidate = self._build_individual()
                # 采样后立即评价，保证进入 new_pop 的个体都带有 objectives/feasible。
                evaluate_mvc_population(self.instance, [candidate], self.mode)
                evaluation_count += 1
                new_pop.append(candidate)
            if not new_pop:
                if stop_reason != "time_limit":
                    stop_reason = "max_evaluations"
                break
            module_runtime["sampling_evaluation"] += clock() - phase_start

            neighborhood_stats: NeighborhoodStats | None = None
            neighborhood_rewards: Dict[str, float] = {}
            budget_remaining = (
                None if self.cfg.max_evaluations is None else self.cfg.max_evaluations - evaluation_count
            )
            if (
                self.cfg.local_search_steps > 0
                and (self.cfg.use_cross_chain_neighbors or self.cfg.use_bottleneck_release)
                and (budget_remaining is None or budget_remaining > 0)
            ):
                phase_start = clock()
                # 局部搜索起点优先来自非支配档案；没有档案时退回当前精英。
                seed_pool = archive.solutions() if self.cfg.use_nd_memory and archive.items else elites
                seeds = self._select_search_seeds(seed_pool, max(1, min(self.cfg.tmax, len(seed_pool))))
                improved = []
                stats_items: List[NeighborhoodStats] = []
                for seed in seeds:
                    # `local_search` 内部会按启用开关生成 MVC 专用邻域，
                    # 并返回改进解以及各邻域的贡献统计。
                    searched, stats = local_search(
                        seed,
                        self.instance,
                        self.mode,
                        self.rng,
                        self.cfg.local_search_steps,
                        neighborhood_probabilities=(
                            self.neighborhood_probabilities if self.cfg.use_adaptive_neighborhood else None
                        ),
                        use_cross_chain_neighbors=self.cfg.use_cross_chain_neighbors,
                        use_critical_migration=self.cfg.use_critical_migration,
                        use_cost_return=self.cfg.use_cost_return,
                        max_evaluations=(
                            None if self.cfg.max_evaluations is None else self.cfg.max_evaluations - evaluation_count
                        ),
                        deadline_s=deadline_s,
                        time_measure=self.cfg.time_measure,
                        return_stats=True,
                    )
                    improved.append(searched)
                    stats_items.append(stats)
                    # 局部搜索内部已经评价若干邻域解，这里把消耗回收到全局评价预算。
                    evaluation_count += stats.evaluations
                    if self.cfg.max_evaluations is not None and evaluation_count >= self.cfg.max_evaluations:
                        break
                    if clock() >= deadline_s:
                        stop_reason = "time_limit"
                        break
                neighborhood_stats = self._merge_neighborhood_stats(stats_items)
                if self.cfg.use_adaptive_neighborhood:
                    neighborhood_rewards = self._update_neighborhood_probabilities(neighborhood_stats)
                new_pop.extend(improved)
                module_runtime["local_search"] += clock() - phase_start

            phase_start = clock()
            if self.cfg.use_nd_memory:
                # 档案保留历史非支配解；把档案解并入候选池可防止优秀解在环境选择中丢失。
                archive.update(new_pop)
                new_pop.extend(archive.solutions())

            # 环境选择：按非支配层填充下一代；最后一层按拥挤距离截断。
            objs = [tuple(ind.objectives or ()) for ind in new_pop]
            fronts = fast_non_dominated_sort(objs)
            next_pop: List[EncodedIndividual] = []
            for front in fronts:
                if len(next_pop) + len(front) <= self.cfg.popsize:
                    next_pop.extend(new_pop[i] for i in front)
                else:
                    # 最后一层放不下时，用拥挤距离保留分布更稀疏的个体，维持 Pareto 前沿多样性。
                    dist = crowding_distance(objs, front)
                    ranked = sorted(zip(front, dist), key=lambda x: x[1], reverse=True)
                    next_pop.extend(new_pop[i] for i, _ in ranked[: self.cfg.popsize - len(next_pop)])
                    break
            pop = next_pop
            if not self.cfg.use_nd_memory:
                # 关闭历史记忆时，档案只反映当前种群的非支配解，用于消融对比。
                archive = NonDominatedArchive(max_size=self.cfg.nd_pool_max)
                archive.update(pop)
            module_runtime["archive_selection"] += clock() - phase_start
            best = [min(float(ind.objectives[d]) for ind in pop if ind.objectives is not None) for d in range(2)]
            row = {
                # history 用浮点保存，便于统一写入 CSV/JSON 并被 pandas 读取。
                "iter": float(it),
                "best_cost": best[0],
                "best_makespan": best[1],
                "nd_size": float(len(archive.items)),
                "evaluation_count": float(evaluation_count),
                "elapsed_s": float(clock() - budget_start),
                "wall_elapsed_s": float(time.perf_counter() - wall_start),
            }
            for module, seconds in module_runtime.items():
                row[f"module_{module}_s"] = float(seconds)
            if neighborhood_stats is not None:
                # 记录邻域概率、奖励和生成/接受次数，用于解释自适应邻域是否生效。
                for kind in NEIGHBORHOOD_KINDS:
                    row[f"nh_prob_{kind}"] = float(self.neighborhood_probabilities.get(kind, 0.0))
                    row[f"nh_reward_{kind}"] = float(neighborhood_rewards.get(kind, 0.0))
                    row[f"nh_accepted_{kind}"] = float(neighborhood_stats.accepted.get(kind, 0))
                    row[f"nh_generated_{kind}"] = float(neighborhood_stats.generated.get(kind, 0))
            history.append(row)
            if clock() >= deadline_s:
                stop_reason = "time_limit"
                break
            if self.cfg.max_evaluations is not None and evaluation_count >= self.cfg.max_evaluations:
                stop_reason = "max_evaluations"
                break

        # 循环结束后再用最终种群更新一次档案，保证最后一代环境选择后的解不遗漏。
        archive.update(pop)
        if not history and stop_reason not in {"time_limit", "max_evaluations"}:
            stop_reason = "completed_without_iteration"
        elapsed_s = time.perf_counter() - wall_start
        budget_elapsed_s = clock() - budget_start
        return MVCEDATSResult(
            nd_solutions=archive.solutions(),
            history=history,
            stop_reason=stop_reason,
            iterations_completed=len(history),
            elapsed_s=elapsed_s,
            evaluation_count=evaluation_count,
            module_runtime_s={**module_runtime, "total": budget_elapsed_s},
            budget_elapsed_s=budget_elapsed_s,
            time_measure=self.cfg.time_measure,
        )
