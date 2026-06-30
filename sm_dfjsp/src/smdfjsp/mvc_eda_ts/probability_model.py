from __future__ import annotations

"""MVC-EDA-TS 的概率模型。

EDA（Estimation of Distribution Algorithm）的核心不是传统交叉/变异，
而是从优质解中估计概率分布，再按这些分布采样新解。

这里维护三类概率：
- PUA: 每个工件选择各候选 SRU 的概率。
- PMS: 每类工件的 OS 序列中，每个工件出现在各位置的概率。
- PMM: 给定 (工件, 工序, SRU) 后选择各候选机器的概率。

MVC 扩展点主要在 PUA：可把价值链内外协同的时间、成本、跨链固定成本
作为先验分布，与精英解统计频率混合。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np

from smdfjsp.core.encoding import build_option_index
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import RNGPack
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.model.mvc_repair import build_mvc_compatible_sru_map


@dataclass
class MVCProbabilityModel:
    """负责维护和更新 MVC-EDA 的 UA/OS/MS 三层概率分布。"""

    instance: MVCSMDFJSPInstance
    mode: MVCModeConfig
    # 默认平滑系数；主算法传入 alpha/beta/gamma 时会覆盖它。
    smoothing: float = 0.15
    # 是否使用基于价值链信息的 PUA 初始先验。
    use_value_chain_prior: bool = True
    # 更新 PUA 时，先验在目标分布中的混合权重。
    prior_weight: float = 0.35
    # softmax 温度，越小越偏向先验评分最优的 SRU。
    prior_temperature: float = 1.0
    # candidates[job_id] 保存该工件在当前 mode 下允许分配的 SRU。
    candidates: Dict[int, List[int]] = field(init=False)
    # pua_prior 是价值链启发式先验；pua 是迭代中持续学习的实际分布。
    pua_prior: Dict[int, np.ndarray] = field(init=False)
    pua: Dict[int, np.ndarray] = field(init=False)
    # pms[type_id][job_id] 表示该工件在本类型 OS 各位置出现的概率。
    pms: Dict[int, Dict[int, np.ndarray]] = field(init=False)
    # kx[type_id] 是该类型所有工序总数，也就是该类型 OS 向量长度。
    kx: Dict[int, int] = field(init=False)
    # pmm[(job_id, op_id, sru_id)] 表示该工序在该 SRU 上选择各机器的概率。
    pmm: Dict[Tuple[int, int, int], np.ndarray] = field(init=False)
    pmm_machines: Dict[Tuple[int, int, int], List[int]] = field(init=False)

    def __post_init__(self) -> None:
        """初始化所有概率矩阵。

        初始化阶段只根据实例结构建立可选项，尚未利用任何搜索结果。
        PUA 可用价值链先验初始化；PMS/PMM 默认均匀分布。
        """

        # 根据跨链模式过滤合法 SRU，例如 cross_chain_allowed=False 时只保留链内 SRU。
        self.candidates = build_mvc_compatible_sru_map(self.instance, self.mode)
        self.pua_prior = self.build_value_chain_prior()
        self.pua = {}
        for job_id, choices in self.candidates.items():
            # PUA 初始分布：有先验就按先验，否则所有候选 SRU 等概率。
            # 这一步相当于把问题数据中的价值链结构注入搜索起点，
            # 但后续 `update` 仍会用精英解频率持续修正它。
            if self.use_value_chain_prior and job_id in self.pua_prior:
                self.pua[job_id] = self.pua_prior[job_id].copy()
            else:
                self.pua[job_id] = np.ones(len(choices), dtype=float) / max(len(choices), 1)
        self.pms = {}
        self.kx = {}
        for type_id, jobs in self.instance.jobs_by_type().items():
            # OS 是按工件类型分层的向量；长度等于该类型所有工序数。
            kx = sum(len(job.operations) for job in jobs)
            self.kx[type_id] = kx
            uniform = np.ones(kx, dtype=float) / max(kx, 1)
            self.pms[type_id] = {job.job_id: uniform.copy() for job in jobs}

        option_index = build_option_index(self.instance)  # type: ignore[arg-type]
        self.pmm = {}
        self.pmm_machines = {}
        for job in self.instance.jobs:
            for op in job.operations:
                for sru_id in self.candidates.get(job.job_id, []):
                    # 只有当该 (job, op, sru) 组合存在可加工机器时才建立 PMM。
                    key = (job.job_id, op.op_id, sru_id)
                    if key not in option_index:
                        continue
                    machines = sorted(option_index[key])
                    self.pmm_machines[key] = machines
                    self.pmm[key] = np.ones(len(machines), dtype=float) / max(len(machines), 1)

    @staticmethod
    def _normalized(values: np.ndarray) -> np.ndarray:
        """把一组指标缩放到 [0, 1]。

        评分模型中成本、时间量纲不同，先归一化再加权相加。
        如果所有值相同，则返回全 0，表示该指标不区分候选 SRU。
        """

        if values.size == 0:
            return values
        low = float(np.min(values))
        high = float(np.max(values))
        if high - low <= 1e-12:
            return np.zeros_like(values, dtype=float)
        return (values.astype(float) - low) / (high - low)

    def build_value_chain_prior(self) -> Dict[int, np.ndarray]:
        """为每个工件构建价值链感知的 SRU 选择先验。

        先验评分越低越好，综合考虑：
        - 估计加工成本；
        - 运输成本；
        - 跨链固定成本；
        - 估计完成时间；
        - 相对链内最优方案的时间收益（收益越大，评分越低）。

        最后用 softmax-like 形式把评分转成概率。
        """

        option_index = build_option_index(self.instance)  # type: ignore[arg-type]
        priors: Dict[int, np.ndarray] = {}
        sru_map = self.instance.sru_map()
        temperature = max(float(self.prior_temperature), 1e-6)
        for job in self.instance.jobs:
            choices = self.candidates.get(job.job_id, [])
            if not choices:
                continue
            proc_costs: List[float] = []
            transport_costs: List[float] = []
            cross_costs: List[float] = []
            completion_estimates: List[float] = []
            for sid in choices:
                # 对每道工序取该 SRU 上最短加工时间/最低加工费用作为粗略估计。
                # 估计阶段不考虑排队冲突，因为 PUA 只需要给“订单选哪个 SRU”提供先验倾向；
                # 精确排队和机器冲突由评价器在个体生成后统一计算。
                proc_time = 0.0
                proc_cost = 0.0
                for op in job.operations:
                    options = option_index.get((job.job_id, op.op_id, sid), {})
                    if not options:
                        continue
                    best_time = min(float(pt) for pt, _ in options.values())
                    best_cost = min(float(pt) * float(cp) for pt, cp in options.values())
                    proc_time += best_time
                    proc_cost += best_cost
                key = (job.job_id, sid)
                proc_costs.append(proc_cost)
                transport_costs.append(float(self.instance.transport_cost.get(key, 0.0)))
                cross_costs.append(float(self.instance.cross_chain_fixed_cost.get(key, 0.0)))
                completion_estimates.append(proc_time + float(self.instance.transport_time.get(key, 0.0)))

            completion_arr = np.array(completion_estimates, dtype=float)
            # intra_best 是链内最优估计完成时间，用于衡量跨链是否真的带来时间收益。
            intra_times = [
                completion_estimates[i]
                for i, sid in enumerate(choices)
                if sru_map[sid].value_chain_id == job.value_chain_id
            ]
            intra_best = min(intra_times) if intra_times else float(np.min(completion_arr))
            gains = np.array([max(0.0, intra_best - x) for x in completion_estimates], dtype=float)
            # 注意 gains 前面是负号：跨链带来的正收益会降低评分，从而提高概率。
            # 权重含义：
            # - 加工成本、运输成本、跨链固定成本越高，候选 SRU 越不优先。
            # - 完成时间越长，候选 SRU 越不优先。
            # - 相对链内最优方案的时间收益越大，候选 SRU 越优先。
            score = (
                0.30 * self._normalized(np.array(proc_costs, dtype=float))
                + 0.25 * self._normalized(np.array(transport_costs, dtype=float))
                + 0.25 * self._normalized(np.array(cross_costs, dtype=float))
                + 0.20 * self._normalized(completion_arr)
                - 0.20 * self._normalized(gains)
            )
            # 将“越低越好”的 score 转换成概率。减去 min(score) 只改善数值稳定性，
            # 不改变候选之间的相对偏好。
            raw = np.exp(-(score - float(np.min(score))) / temperature)
            if float(raw.sum()) <= 0.0:
                priors[job.job_id] = np.ones(len(choices), dtype=float) / max(len(choices), 1)
            else:
                priors[job.job_id] = raw / raw.sum()
        return priors

    @staticmethod
    def _sample(values: List[int], probs: np.ndarray, rng: RNGPack, theta_max: float = 1.0) -> int:
        """按离散概率分布采样一个值。

        `theta_max` 保留给旧版 EDA 的截断采样逻辑；默认 1.0 等价于普通轮盘赌。
        """

        if not values:
            raise ValueError("Cannot sample from an empty MVC probability vector")
        total = float(probs.sum())
        if total <= 0.0:
            return int(rng.py_rng.choice(values))
        cdf = np.cumsum(probs.astype(float) / total)
        theta = rng.py_rng.random() * float(theta_max)
        for value, bound in zip(values, cdf):
            if theta <= float(bound):
                return int(value)
        return int(values[-1])

    def sample_ua(self, rng: RNGPack) -> Dict[int, int]:
        """按当前 PUA 为每个工件采样 SRU 分配。"""

        ua: Dict[int, int] = {}
        for job in self.instance.jobs:
            choices = self.candidates[job.job_id]
            probs = self.pua[job.job_id]
            ua[job.job_id] = self._sample(choices, probs, rng)
        return ua

    def sample_os(self, rng: RNGPack) -> Dict[int, List[int]]:
        """按当前 PMS 采样 OS 层。

        对同一类型的每个工件，需要在 OS 向量里出现 `工序数` 次。
        采样时逐个占用位置，最后补齐因概率冲突留下的空位，保证 OS 合法。
        """

        os_layer: Dict[int, List[int]] = {}
        for type_id, jobs in self.instance.jobs_by_type().items():
            kx = self.kx[type_id]
            vec = [-1] * kx
            positions = list(range(kx))
            for job in jobs:
                for _ in range(len(job.operations)):
                    if not positions:
                        break
                    probs = self.pms[type_id][job.job_id]
                    cdf = np.cumsum(probs.astype(float) / max(float(probs.sum()), 1e-12))
                    theta = rng.py_rng.random() * max(float(cdf[p]) for p in positions)
                    pos = positions[-1]
                    for cand_pos in positions:
                        if theta <= float(cdf[cand_pos]):
                            pos = cand_pos
                            break
                    positions.remove(pos)
                    vec[pos] = job.job_id

            # 防御性补齐：如果某些位置未填，按每个工件还缺的出现次数随机填入。
            counts: Dict[int, int] = {}
            for job_id in vec:
                if job_id != -1:
                    counts[job_id] = counts.get(job_id, 0) + 1
            missing: List[int] = []
            for job in jobs:
                missing.extend([job.job_id] * max(0, len(job.operations) - counts.get(job.job_id, 0)))
            rng.py_rng.shuffle(missing)
            cursor = 0
            for idx, job_id in enumerate(vec):
                if job_id == -1:
                    vec[idx] = missing[cursor]
                    cursor += 1
            os_layer[type_id] = vec
        return os_layer

    def sample_ms(self, op_layer: Dict[int, List[Tuple[int, int]]], rng: RNGPack) -> Dict[int, List[int]]:
        """按当前 PMM 为 OP 队列中的每道工序采样机器。"""

        option_index = build_option_index(self.instance)  # type: ignore[arg-type]
        ms: Dict[int, List[int]] = {}
        for sru_id, seq in op_layer.items():
            vec: List[int] = []
            for job_id, op_id in seq:
                key = (job_id, op_id, sru_id)
                machines = self.pmm_machines.get(key)
                probs = self.pmm.get(key)
                if machines and probs is not None:
                    vec.append(self._sample(machines, probs, rng))
                else:
                    vec.append(int(rng.py_rng.choice(list(option_index[key]))))
            ms[sru_id] = vec
        return ms

    def update(self, elites: List[EncodedIndividual], alpha: float | None = None, beta: float | None = None, gamma: float | None = None) -> None:
        """用精英解集合更新 PUA/PMS/PMM。

        更新形式是指数平滑：
        `new_distribution = (1 - learning_rate) * old + learning_rate * observed_frequency`

        这样既学习精英解的统计规律，也保留一部分探索概率。
        """

        if not elites:
            return
        alpha = self.smoothing if alpha is None else float(alpha)
        beta = self.smoothing if beta is None else float(beta)
        gamma = self.smoothing if gamma is None else float(gamma)

        for job_id, choices in self.candidates.items():
            # 统计精英解中每个工件被分配到各候选 SRU 的频率。
            pos = {sid: i for i, sid in enumerate(choices)}
            freq = np.zeros(len(choices), dtype=float)
            for ind in elites:
                sid = ind.ua.get(job_id)
                if sid in pos:
                    freq[pos[sid]] += 1.0
            if freq.sum() <= 0:
                continue
            freq /= freq.sum()
            if self.use_value_chain_prior and job_id in self.pua_prior:
                # PUA 的目标分布不是纯频率，而是频率与价值链先验的加权混合。
                # 这样可以避免早期精英样本过少时把概率模型拉向偶然选择；
                # 同时随着精英频率稳定，`1 - prior_weight` 部分会保留搜索经验。
                prior_weight = min(max(float(self.prior_weight), 0.0), 1.0)
                target = (1.0 - prior_weight) * freq + prior_weight * self.pua_prior[job_id]
                target = target / max(float(target.sum()), 1e-12)
            else:
                target = freq
            old = self.pua[job_id]
            new = (1.0 - alpha) * old + alpha * target
            new = np.maximum(new, 1e-9)
            self.pua[job_id] = new / new.sum()

        jobs_by_type = self.instance.jobs_by_type()
        for type_id, jobs in jobs_by_type.items():
            kx = self.kx[type_id]
            for job in jobs:
                # 统计某工件在 OS 各位置出现的概率。
                # 除以工序数，是为了让每个精英个体对该工件贡献总量为 1。
                freq = np.zeros(kx, dtype=float)
                for ind in elites:
                    vec = ind.os.get(type_id, [])
                    for pos, token in enumerate(vec):
                        if token == job.job_id:
                            freq[pos] += 1.0 / max(len(job.operations), 1)
                if freq.sum() <= 0:
                    continue
                freq /= freq.sum()
                old = self.pms[type_id][job.job_id]
                new = (1.0 - beta) * old + beta * freq
                new = np.maximum(new, 1e-9)
                self.pms[type_id][job.job_id] = new / new.sum()

        for key, old in list(self.pmm.items()):
            # PMM 只从真正把该工件分配到该 SRU 的精英解中学习机器选择频率。
            # 如果某个 (job, op, sru) 组合在精英中从未出现，不强行更新，
            # 保留原有概率可以维持少量探索机会。
            machines = self.pmm_machines[key]
            pos = {machine_id: i for i, machine_id in enumerate(machines)}
            freq = np.zeros(len(machines), dtype=float)
            assigned_count = 0.0
            job_id, op_id, sru_id = key
            for ind in elites:
                if ind.ua.get(job_id) != sru_id:
                    continue
                assigned_count += 1.0
                seq = ind.op.get(sru_id, [])
                ms_vec = ind.ms.get(sru_id, [])
                for idx, token in enumerate(seq):
                    if token == (job_id, op_id) and idx < len(ms_vec) and ms_vec[idx] in pos:
                        freq[pos[ms_vec[idx]]] += 1.0
            if assigned_count <= 0.0:
                continue
            freq /= assigned_count
            new = (1.0 - gamma) * old + gamma * freq
            new = np.maximum(new, 1e-9)
            self.pmm[key] = new / new.sum()
