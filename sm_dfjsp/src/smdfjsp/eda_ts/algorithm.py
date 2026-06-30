from __future__ import annotations

"""Plain EDA-TS 算法实现。

这是不含 MVC 专用价值链机制的 EDA-TS 基线版本，主要用于复现和消融对比。
算法思想：
1. 使用三层概率矩阵生成四层编码个体。
2. 用非支配排序选择精英，更新概率矩阵。
3. 可选地维护历史非支配记忆池。
4. 可选地对非支配解做禁忌搜索强化。

编码含义：
- UA: 工件到 SRU 的分配。
- OS: 各类型工件的工序顺序 token 序列。
- OP: 由 UA+OS 派生出来的 SRU 工序队列。
- MS: 每个 SRU 队列中各工序的机器选择。
"""

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from smdfjsp.core.encoding import (
    build_compatible_sru_map,
    build_option_index,
    build_random_individual,
    op_from_ua_os,
    random_ua,
    repair_individual,
)
from smdfjsp.core.pareto import crowding_distance, dominates, fast_non_dominated_sort, merge_non_dominated
from smdfjsp.core.random_utils import RNGPack, make_rng
from smdfjsp.core.types import EncodedIndividual, ObjPair, SMDFJSPInstance
from smdfjsp.model.evaluator import evaluate_individual


@dataclass
class EDATSConfig:
    """Plain EDA-TS 的参数配置。"""

    popsize: int = 50
    # 最大迭代次数；运行还受 time_limit_s 限制。
    max_iter: int = 100
    time_limit_s: float = 100.0
    # 三类概率矩阵的学习率。
    alpha: float = 0.5  # PMA lr
    beta: float = 0.5  # PMS lr
    gamma: float = 0.5  # PMM lr
    # 每代用于概率更新的精英比例。
    mu: float = 0.1  # elite rate
    # 禁忌搜索中长期记忆的惩罚系数。
    epsilon: float = 0.008  # penalty factor
    # 每代禁忌搜索起点数/局部步数相关参数。
    tmax: int = 10  # TS starts per generation
    nd_pool_max: int = 300
    seed: int = 42
    use_multi_population: bool = True
    use_nd_memory: bool = True
    use_ts: bool = True
    trace_enabled: bool = False
    trace_dir: Optional[str] = None
    trace_every: int = 1


@dataclass
class RunResult:
    """Plain EDA-TS 的运行结果。"""

    nd_solutions: List[EncodedIndividual]
    history: List[Dict[str, float]]
    trace_file: Optional[str] = None


class EDATS:
    """Plain EDA-TS 求解器。"""

    def __init__(self, instance: SMDFJSPInstance, config: EDATSConfig):
        self.instance = instance
        self.cfg = config
        self.rng: RNGPack = make_rng(config.seed)
        self.option_index = build_option_index(instance)
        self.job_map = instance.job_map()
        self.sru_map = instance.sru_map()
        self.jobs_by_type = instance.jobs_by_type()
        self.srus_by_type = instance.srus_by_type()
        # 每个工件可分配的 SRU 集合，后续 PMA/UA 采样都基于这个集合。
        self.compatible_srus = build_compatible_sru_map(instance, self.option_index)
        self._init_probability_matrices()
        self._trace_file: Optional[Path] = None
        if self.cfg.trace_enabled and self.cfg.trace_dir:
            trace_dir = Path(self.cfg.trace_dir)
            trace_dir.mkdir(parents=True, exist_ok=True)
            stamp = int(time.time() * 1000)
            self._trace_file = trace_dir / f"edats_trace_seed{self.cfg.seed}_{stamp}.jsonl"

    @staticmethod
    def _copy_individual(ind: EncodedIndividual) -> EncodedIndividual:
        """复制个体的四层编码和 aux 元数据，避免邻域操作污染原个体。"""

        return EncodedIndividual(
            ua=dict(ind.ua),
            os={k: list(v) for k, v in ind.os.items()},
            op={k: list(v) for k, v in ind.op.items()},
            ms={k: list(v) for k, v in ind.ms.items()},
            aux=dict(ind.aux),
        )

    @staticmethod
    def _entropy(values: np.ndarray) -> float:
        """计算概率向量熵，用于 trace 中观察概率模型是否过早收敛。"""

        if values.size == 0:
            return 0.0
        arr = values.astype(float)
        arr = arr[arr > 0.0]
        if arr.size == 0:
            return 0.0
        return float(-(arr * np.log(arr)).sum())

    def _sample_by_cumulative(self, values: Sequence[int], probs: np.ndarray, theta_max: float = 1.0) -> int:
        """按累积分布轮盘赌采样一个离散值。"""

        total = float(probs.sum())
        if not values:
            raise ValueError("Cannot sample from an empty sequence")
        if total <= 0.0:
            return int(self.rng.py_rng.choice(list(values)))
        cdf = np.cumsum(probs.astype(float) / total)
        theta = self.rng.py_rng.random() * float(theta_max)
        for value, bound in zip(values, cdf):
            if theta <= float(bound):
                return int(value)
        return int(values[-1])

    def _trace_snapshot(self, it: int, en_size: int, nd_size: int) -> None:
        """按配置输出概率矩阵快照，便于调试 EDA 学习过程。"""

        if not self.cfg.trace_enabled:
            return
        every = max(1, int(self.cfg.trace_every))
        if it % every != 0:
            return

        pma_entropy = []
        pms_entropy = []
        pmm_entropy = []
        for t in self.pma:
            for j in self.pma[t]:
                pma_entropy.append(self._entropy(self.pma[t][j]))
        for t in self.pms:
            for j in self.pms[t]:
                pms_entropy.append(self._entropy(self.pms[t][j]))
        for key in self.pmm:
            pmm_entropy.append(self._entropy(self.pmm[key]))

        payload: Dict[str, Any] = {
            "iter": it,
            "seed": int(self.cfg.seed),
            "en_size": int(en_size),
            "nd_size": int(nd_size),
            "pma_entropy_mean": (sum(pma_entropy) / len(pma_entropy) if pma_entropy else 0.0),
            "pms_entropy_mean": (sum(pms_entropy) / len(pms_entropy) if pms_entropy else 0.0),
            "pmm_entropy_mean": (sum(pmm_entropy) / len(pmm_entropy) if pmm_entropy else 0.0),
            "pma": {
                str(t): {str(j): [float(x) for x in self.pma[t][j]] for j in sorted(self.pma[t])}
                for t in sorted(self.pma)
            },
            "pms": {
                str(t): {str(j): [float(x) for x in self.pms[t][j]] for j in sorted(self.pms[t])}
                for t in sorted(self.pms)
            },
            "pmm": {
                f"{j}-{o}-{s}": [float(x) for x in self.pmm[(j, o, s)]]
                for (j, o, s) in sorted(self.pmm)
            },
        }
        line = json.dumps(payload, ensure_ascii=False)
        if self._trace_file is not None:
            with self._trace_file.open("a", encoding="utf-8") as f:
                f.write(line + "\n")

    def _init_probability_matrices(self) -> None:
        """初始化 PMA/PMS/PMM 三类概率矩阵。

        PMA 对应 UA 层，学习“工件分配到哪个 SRU”。
        PMS 对应 OS 层，学习“工件 token 更倾向出现在哪些位置”。
        PMM 对应 MS 层，学习“某工件工序在某 SRU 上选择哪台机器”。
        """

        # PMA[x][job_id] -> probabilities over compatible sru ids for this job
        self.pma: Dict[int, Dict[int, np.ndarray]] = {}
        self.pma_srus: Dict[int, List[int]] = {}
        for t, jobs in self.jobs_by_type.items():
            self.pma[t] = {}
            for j in jobs:
                sru_ids = list(self.compatible_srus.get(j.job_id, []))
                if not sru_ids:
                    sru_ids = [s.sru_id for s in self.srus_by_type[t]]
                self.pma_srus[j.job_id] = sru_ids
                uniform = np.ones(len(sru_ids), dtype=float) / len(sru_ids)
                self.pma[t][j.job_id] = uniform.copy()

        # PMS[x][job_id] -> probabilities on positions in OS vector of type x
        self.pms: Dict[int, Dict[int, np.ndarray]] = {}
        self.kx: Dict[int, int] = {}
        for t, jobs in self.jobs_by_type.items():
            kx = sum(len(j.operations) for j in jobs)
            self.kx[t] = kx
            uniform = np.ones(kx, dtype=float) / max(kx, 1)
            self.pms[t] = {j.job_id: uniform.copy() for j in jobs}

        # PMM[(job_id, op_id, sru_id)] -> probabilities over machines
        self.pmm: Dict[Tuple[int, int, int], np.ndarray] = {}
        self.pmm_machines: Dict[Tuple[int, int, int], List[int]] = {}
        for job in self.instance.jobs:
            for op in job.operations:
                for sru_id in self.compatible_srus.get(job.job_id, []):
                    key = (job.job_id, op.op_id, sru_id)
                    if key not in self.option_index:
                        continue
                    m_dict = self.option_index[key]
                    machines = sorted(m_dict.keys())
                    self.pmm_machines[key] = machines
                    self.pmm[key] = np.ones(len(machines), dtype=float) / len(machines)

    def _sample_ua(self) -> Dict[int, int]:
        """从 PMA 中采样 UA 层。"""

        ua: Dict[int, int] = {}
        for t, jobs in self.jobs_by_type.items():
            for j in jobs:
                sru_ids = self.pma_srus[j.job_id]
                probs = self.pma[t][j.job_id]
                ua[j.job_id] = self._sample_by_cumulative(sru_ids, probs)
        return ua

    def _md_ua(self) -> Dict[int, int]:
        """最小运输时间启发式 UA，用于多源种群生成。"""

        ua: Dict[int, int] = {}
        for job in self.instance.jobs:
            candidates = self.compatible_srus.get(job.job_id, [])
            if not candidates:
                candidates = [s.sru_id for s in self.srus_by_type[job.type_id]]
            best = min(candidates, key=lambda sid: self.instance.transport_time[(job.job_id, sid)])
            ua[job.job_id] = best
        return ua

    def _sample_os(self) -> Dict[int, List[int]]:
        """从 PMS 中采样 OS 层。

        每个工件 token 需要出现等于其工序数的次数。
        采样过程逐步占用位置，最后补齐未填位置，保证 OS 编码合法。
        """

        os_layer: Dict[int, List[int]] = {}
        for t, jobs in self.jobs_by_type.items():
            kx = self.kx[t]
            vec = [-1] * kx
            positions = list(range(kx))
            for j in jobs:
                remain = len(j.operations)
                for _ in range(remain):
                    probs = self.pms[t][j.job_id]
                    if not positions:
                        break
                    sps = np.cumsum(probs.astype(float) / max(float(probs.sum()), 1e-12))
                    theta = self.rng.py_rng.random() * max(float(sps[p]) for p in positions)
                    pos = positions[-1]
                    for cand_pos in positions:
                        if theta <= float(sps[cand_pos]):
                            pos = cand_pos
                            break
                    positions.remove(pos)
                    vec[pos] = j.job_id
            # Fill any leftover by random valid token.
            missing = []
            cnt = {}
            for job_id in vec:
                if job_id != -1:
                    cnt[job_id] = cnt.get(job_id, 0) + 1
            for j in jobs:
                need = len(j.operations) - cnt.get(j.job_id, 0)
                if need > 0:
                    missing.extend([j.job_id] * need)
            self.rng.py_rng.shuffle(missing)
            miss_cursor = 0
            for i, v in enumerate(vec):
                if v == -1:
                    vec[i] = missing[miss_cursor]
                    miss_cursor += 1
            os_layer[t] = vec
        return os_layer

    def _sample_ms(self, op_layer: Dict[int, List[Tuple[int, int]]]) -> Dict[int, List[int]]:
        """从 PMM 中采样 MS 层。"""

        ms: Dict[int, List[int]] = {}
        for sru_id, seq in op_layer.items():
            vec: List[int] = []
            for job_id, op_id in seq:
                key = (job_id, op_id, sru_id)
                machines = self.pmm_machines.get(key)
                probs = self.pmm.get(key)
                if machines and probs is not None:
                    vec.append(self._sample_by_cumulative(machines, probs))
                    continue
                options = self.option_index.get(key, {})
                if options:
                    vec.append(int(self.rng.py_rng.choice(list(options.keys()))))
            ms[sru_id] = vec
        return ms

    def _mc_ms(self, op_layer: Dict[int, List[Tuple[int, int]]]) -> Dict[int, List[int]]:
        """选择加工成本最低的机器，成本近似为 processing_time * cost_rate。"""

        ms: Dict[int, List[int]] = {}
        for sru_id, seq in op_layer.items():
            vec: List[int] = []
            for job_id, op_id in seq:
                m_dict = self.option_index[(job_id, op_id, sru_id)]
                best_machine = min(m_dict.keys(), key=lambda m: m_dict[m][0] * m_dict[m][1])
                vec.append(best_machine)
            ms[sru_id] = vec
        return ms

    def _mct_ms(self, ua: Dict[int, int], op_layer: Dict[int, List[Tuple[int, int]]]) -> Dict[int, List[int]]:
        """贪心选择预计完工时间最早的机器。"""

        ms: Dict[int, List[int]] = {}
        machine_ready: Dict[Tuple[int, int], float] = {}
        job_ready: Dict[int, float] = {j.job_id: 0.0 for j in self.instance.jobs}
        for sru_id, seq in op_layer.items():
            vec: List[int] = []
            for job_id, op_id in seq:
                m_dict = self.option_index[(job_id, op_id, sru_id)]
                best_m = None
                best_end = float("inf")
                for m, (pt, _) in m_dict.items():
                    st = max(job_ready[job_id], machine_ready.get((sru_id, m), 0.0))
                    en = st + pt
                    if en < best_end:
                        best_end = en
                        best_m = m
                vec.append(best_m)  # type: ignore[arg-type]
                machine_ready[(sru_id, best_m)] = best_end  # type: ignore[arg-type]
                job_ready[job_id] = best_end
            ms[sru_id] = vec
        return ms

    def _build_individual(self) -> EncodedIndividual:
        """构造一个新个体。

        开启多源种群时：
        - UA 80% 来自 PMA，20% 来自最小运输时间启发式。
        - MS 60% 来自 PMM，20% 成本优先，20% 完工时间优先。
        这种混合能在 EDA 学习之外保留启发式探索能力。
        """

        if self.cfg.use_multi_population:
            # UA: Sampling 80%, MD 20%
            ua = self._sample_ua() if self.rng.py_rng.random() < 0.8 else self._md_ua()
            os_layer = self._sample_os()
            op = op_from_ua_os(self.instance, ua, os_layer)
            # MS: Sampling 60%, MC 20%, MCT 20%
            r = self.rng.py_rng.random()
            if r < 0.6:
                ms = self._sample_ms(op)
            elif r < 0.8:
                ms = self._mc_ms(op)
            else:
                ms = self._mct_ms(ua, op)
        else:
            ua = self._sample_ua()
            os_layer = self._sample_os()
            op = op_from_ua_os(self.instance, ua, os_layer)
            ms = self._sample_ms(op)
        ind = EncodedIndividual(ua=ua, os=os_layer, op=op, ms=ms)
        return repair_individual(ind, self.instance, self.option_index, self.rng)

    @staticmethod
    def _evaluate_population(instance: SMDFJSPInstance, pop: List[EncodedIndividual]) -> None:
        """批量评价种群，并把目标值/可行性写回个体。"""

        for ind in pop:
            result = evaluate_individual(instance, ind)
            ind.objectives = result.objectives
            ind.feasible = result.feasible

    def _select_elite(self, pop: List[EncodedIndividual], elite_size: int) -> List[EncodedIndividual]:
        """使用非支配排序和拥挤距离选择精英学习集。"""

        objs = [ind.objectives for ind in pop]  # type: ignore[list-item]
        fronts = fast_non_dominated_sort(objs)  # type: ignore[arg-type]
        selected: List[EncodedIndividual] = []
        for front in fronts:
            if len(selected) + len(front) <= elite_size:
                selected.extend(pop[i] for i in front)
            else:
                distances = crowding_distance(objs, front)  # type: ignore[arg-type]
                pairs = sorted(zip(front, distances), key=lambda x: x[1], reverse=True)
                for i, _ in pairs[: elite_size - len(selected)]:
                    selected.append(pop[i])
                break
        return selected

    @staticmethod
    def _rank_by_front_and_crowding(objs: Sequence[ObjPair]) -> List[int]:
        """按 Pareto 层级和拥挤距离排序候选。"""

        fronts = fast_non_dominated_sort(objs)
        ranked: List[int] = []
        for front in fronts:
            distances = crowding_distance(objs, front)
            pairs = sorted(zip(front, distances), key=lambda x: x[1], reverse=True)
            ranked.extend(i for i, _ in pairs)
        return ranked

    def _select_ts_seeds(
        self,
        pool: Sequence[Tuple[ObjPair, EncodedIndividual]],
        count: int,
    ) -> List[EncodedIndividual]:
        """从非支配池的稀疏区域选择禁忌搜索起点。"""

        if not pool or count <= 0:
            return []
        objs = [x[0] for x in pool]
        ranked = self._rank_by_front_and_crowding(objs)
        return [pool[i][1] for i in ranked[: min(count, len(ranked))]]

    def _update_probability_matrices(self, en: List[EncodedIndividual]) -> None:
        """用精英集/记忆池更新 PMA/PMS/PMM。

        更新采用指数平滑：新矩阵 = 旧矩阵保留项 + 精英频率学习项。
        这样既能学习优秀解的结构，也能保留一定随机探索概率。
        """

        # PMA
        for t, jobs in self.jobs_by_type.items():
            for j in jobs:
                sru_ids = self.pma_srus[j.job_id]
                sru_pos = {sid: i for i, sid in enumerate(sru_ids)}
                freq = np.zeros(len(sru_ids), dtype=float)
                for ind in en:
                    sid = ind.ua[j.job_id]
                    if sid in sru_pos:
                        freq[sru_pos[sid]] += 1.0
                if freq.sum() > 0:
                    freq /= freq.sum()
                self.pma[t][j.job_id] = (1.0 - self.cfg.alpha) * self.pma[t][j.job_id] + self.cfg.alpha * freq
                self.pma[t][j.job_id] /= self.pma[t][j.job_id].sum()

        # PMS
        for t, jobs in self.jobs_by_type.items():
            kx = self.kx[t]
            for j in jobs:
                freq = np.zeros(kx, dtype=float)
                for ind in en:
                    vec = ind.os[t]
                    for pos, token in enumerate(vec):
                        if token == j.job_id:
                            freq[pos] += 1.0 / len(j.operations)
                if freq.sum() > 0:
                    freq /= freq.sum()
                self.pms[t][j.job_id] = (1.0 - self.cfg.beta) * self.pms[t][j.job_id] + self.cfg.beta * freq
                if self.pms[t][j.job_id].sum() <= 0:
                    self.pms[t][j.job_id] = np.ones(kx) / kx
                else:
                    self.pms[t][j.job_id] /= self.pms[t][j.job_id].sum()

        # PMM
        for key, base in self.pmm.items():
            machines = self.pmm_machines[key]
            mpos = {m: i for i, m in enumerate(machines)}
            freq = np.zeros(len(machines), dtype=float)
            assigned_count = 0.0
            for ind in en:
                if ind.ua.get(key[0]) != key[2]:
                    continue
                assigned_count += 1.0
                sru_id = key[2]
                seq = ind.op.get(sru_id, [])
                ms_vec = ind.ms.get(sru_id, [])
                for i, item in enumerate(seq):
                    if item == (key[0], key[1]) and i < len(ms_vec):
                        m = ms_vec[i]
                        if m in mpos:
                            freq[mpos[m]] += 1.0
            if assigned_count <= 0.0:
                self.pmm[key] = base.copy()
                continue
            freq /= assigned_count
            self.pmm[key] = (1.0 - self.cfg.gamma) * base + self.cfg.gamma * freq
            self.pmm[key] /= self.pmm[key].sum()

    def _neighbor_structure_i(self, ind: EncodedIndividual) -> List[EncodedIndividual]:
        """N1：在同类型兼容 SRU 之间重新分配工件。"""

        neighbors: List[EncodedIndividual] = []
        for t, jobs in self.jobs_by_type.items():
            candidates = jobs[:]
            self.rng.py_rng.shuffle(candidates)
            take = min(5, len(candidates))
            for job in candidates[:take]:
                possible = [sid for sid in self.compatible_srus.get(job.job_id, []) if sid != ind.ua[job.job_id]]
                if not possible:
                    continue
                moved = self._copy_individual(ind)
                from_sru = int(ind.ua[job.job_id])
                to_sru = int(self.rng.py_rng.choice(possible))
                moved.ua[job.job_id] = to_sru
                moved.op = op_from_ua_os(self.instance, moved.ua, moved.os)
                moved.ms = self._sample_ms(moved.op)
                moved.aux.update(
                    {
                        "move_kind": "N1",
                        "job_id": int(job.job_id),
                        "from_sru": from_sru,
                        "to_sru": to_sru,
                    }
                )
                neighbors.append(repair_individual(moved, self.instance, self.option_index, self.rng))
        return neighbors

    def _neighbor_structure_ii(self, ind: EncodedIndividual) -> List[EncodedIndividual]:
        """N2：OS 插入移动，改变工件 token 在序列中的位置。"""

        neighbors: List[EncodedIndividual] = []
        for t, vec in ind.os.items():
            if len(vec) < 2:
                continue
            n_try = min(5, len(vec))
            for _ in range(n_try):
                i1 = self.rng.py_rng.randrange(len(vec))
                i2 = self.rng.py_rng.randrange(len(vec))
                if i1 == i2:
                    continue
                new_vec = list(vec)
                token = new_vec.pop(i1)
                new_vec.insert(i2, token)
                moved = EncodedIndividual(
                    ua=dict(ind.ua),
                    os={k: (new_vec if k == t else list(v)) for k, v in ind.os.items()},
                    op={},
                    ms={},
                    aux={
                        "move_kind": "N2",
                        "type_id": int(t),
                        "from_pos": int(i1),
                        "to_pos": int(i2),
                        "job_id": int(token),
                    },
                )
                moved.op = op_from_ua_os(self.instance, moved.ua, moved.os)
                moved.ms = self._sample_ms(moved.op)
                neighbors.append(repair_individual(moved, self.instance, self.option_index, self.rng))
        return neighbors

    def _neighbor_structure_iii(self, ind: EncodedIndividual) -> List[EncodedIndividual]:
        """N3：MS 机器替换，给某道工序换另一台兼容机器。"""

        neighbors: List[EncodedIndividual] = []
        for sru_id, seq in ind.op.items():
            if not seq:
                continue
            n_try = min(5, len(seq))
            for _ in range(n_try):
                i = self.rng.py_rng.randrange(len(seq))
                job_id, op_id = seq[i]
                options = list(self.option_index[(job_id, op_id, sru_id)].keys())
                if len(options) <= 1:
                    continue
                moved = self._copy_individual(ind)
                current = moved.ms[sru_id][i]
                choices = [m for m in options if m != current]
                to_machine = int(self.rng.py_rng.choice(choices))
                moved.ms[sru_id][i] = to_machine
                moved.aux.update(
                    {
                        "move_kind": "N3",
                        "sru_id": int(sru_id),
                        "job_id": int(job_id),
                        "op_id": int(op_id),
                        "from_machine": int(current),
                        "to_machine": to_machine,
                    }
                )
                neighbors.append(repair_individual(moved, self.instance, self.option_index, self.rng))
        return neighbors

    def _penalized(self, obj: ObjPair, freq: int) -> ObjPair:
        """对重复导致变差的移动施加长期记忆惩罚。"""

        return (obj[0] + self.cfg.epsilon * obj[0] * freq, obj[1] + self.cfg.epsilon * obj[1] * freq)

    @staticmethod
    def _build_tabu_key(ind: EncodedIndividual) -> Optional[Tuple]:
        """构造禁忌表 key。

        当前只对 OS 插入移动建立显式禁忌，避免相同插入移动短期反复出现。
        """

        mk = str(ind.aux.get("move_kind", ""))
        if mk == "N2":
            return (
                "N2",
                int(ind.aux["type_id"]),
                int(ind.aux["job_id"]),
                int(ind.aux["from_pos"]),
                int(ind.aux["to_pos"]),
            )
        return None

    def _tabu_search(self, initial: EncodedIndividual) -> EncodedIndividual:
        """从一个初始解出发执行禁忌搜索强化。

        每一步生成 N1/N2/N3 三类邻居，评价后按非支配排序选择候选。
        禁忌表用于避免短期循环，长期记忆用于惩罚反复导致变差的 SRU/机器选择。
        搜索结束后返回局部非支配档案中排序最靠前的个体。
        """

        current = initial
        current_eval = evaluate_individual(self.instance, current)
        current.objectives = current_eval.objectives
        best = current
        best_obj = current.objectives
        local_nd: List[Tuple[ObjPair, EncodedIndividual]] = []
        if current.objectives is not None:
            local_nd = merge_non_dominated([], [(current.objectives, current)])

        t_list: List[Tuple] = []
        lmls: Dict[Tuple[int, int], int] = {}
        lmlm: Dict[Tuple[int, int, int, int], int] = {}
        t_max_len = max(1, sum(min(5, self.kx[t]) for t in self.kx))

        for _ in range(max(1, self.cfg.tmax)):
            # 生成三类局部邻域并统一评价。
            n1 = self._neighbor_structure_i(current)
            n2 = self._neighbor_structure_ii(current)
            n3 = self._neighbor_structure_iii(current)
            neighbors = n1 + n2 + n3
            if not neighbors:
                break
            self._evaluate_population(self.instance, neighbors)

            scored: List[Tuple[ObjPair, EncodedIndividual]] = []
            for nb in neighbors:
                # 如果候选比 current 差，则根据长期记忆频率增加惩罚目标。
                obj = nb.objectives  # type: ignore[assignment]
                pen = 0
                mk = str(nb.aux.get("move_kind", ""))
                is_worse = bool(current.objectives is not None and dominates(current.objectives, obj))
                if is_worse and mk == "N1":
                    pen += lmls.get((int(nb.aux["to_sru"]), int(nb.aux["job_id"])), 0)
                elif is_worse and mk == "N3":
                    pen += lmlm.get(
                        (
                            int(nb.aux["sru_id"]),
                            int(nb.aux["job_id"]),
                            int(nb.aux["op_id"]),
                            int(nb.aux["to_machine"]),
                        ),
                        0,
                    )
                scored.append((self._penalized(obj, pen), nb))
            local_nd = merge_non_dominated(
                local_nd,
                [(nb.objectives, nb) for nb in neighbors if nb.objectives is not None],
                max_size=max(1, self.cfg.nd_pool_max),
            )
            candidate_order = self._rank_by_front_and_crowding([x[0] for x in scored])
            chosen = None
            for cand_idx in candidate_order:
                cand = scored[cand_idx][1]
                tabu_key = self._build_tabu_key(cand)
                # Aspiration criterion: allow tabu move if it improves current best.
                improves_best = dominates(cand.objectives, best_obj)  # type: ignore[arg-type]
                is_tabu = tabu_key is not None and tabu_key in t_list
                if not is_tabu or improves_best:
                    chosen = cand
                    if tabu_key is not None:
                        if tabu_key in t_list:
                            t_list.remove(tabu_key)
                        t_list.append(tabu_key)
                        if len(t_list) > t_max_len:
                            t_list.pop(0)
                    break
            if chosen is None:
                chosen = scored[candidate_order[0]][1]
            # Update long-memory frequencies by neighborhood move type.
            mk = str(chosen.aux.get("move_kind", ""))
            if mk == "N1":
                key = (int(chosen.aux["to_sru"]), int(chosen.aux["job_id"]))
                lmls[key] = lmls.get(key, 0) + 1
            elif mk == "N3":
                key = (
                    int(chosen.aux["sru_id"]),
                    int(chosen.aux["job_id"]),
                    int(chosen.aux["op_id"]),
                    int(chosen.aux["to_machine"]),
                )
                lmlm[key] = lmlm.get(key, 0) + 1

            current = chosen
            if dominates(current.objectives, best_obj):  # type: ignore[arg-type]
                best = current
                best_obj = current.objectives
        if local_nd:
            local_objs = [x[0] for x in local_nd]
            ranked_local = self._rank_by_front_and_crowding(local_objs)
            return local_nd[ranked_local[0]][1]
        return best

    def run(self) -> RunResult:
        """执行 Plain EDA-TS 主循环。

        流程：
        1. 初始化种群并评价。
        2. 维护非支配记忆池。
        3. 每代选择精英并更新概率矩阵。
        4. 采样新种群，必要时做禁忌搜索强化。
        5. 用非支配排序和拥挤距离做环境选择。
        """

        start = time.time()
        pop = [self._build_individual() for _ in range(self.cfg.popsize)]
        self._evaluate_population(self.instance, pop)
        nd_pool: List[Tuple[ObjPair, EncodedIndividual]] = []
        if self.cfg.use_nd_memory:
            nd_pool = merge_non_dominated(
                [],
                [(ind.objectives, ind) for ind in pop if ind.objectives is not None],
                max_size=self.cfg.nd_pool_max,
            )
        history: List[Dict[str, float]] = []

        for it in range(1, self.cfg.max_iter + 1):
            # 时间预算优先于代数预算。
            if (time.time() - start) >= self.cfg.time_limit_s:
                break
            elite_size = max(1, int(self.cfg.mu * self.cfg.popsize))
            elites = self._select_elite(pop, elite_size)
            # 学习集由当前精英和历史非支配记忆共同组成。
            en = elites + ([x[1] for x in nd_pool] if self.cfg.use_nd_memory else [])
            self._update_probability_matrices(en)
            self._trace_snapshot(it=it, en_size=len(en), nd_size=len(nd_pool))

            new_pop = [self._build_individual() for _ in range(self.cfg.popsize)]
            self._evaluate_population(self.instance, new_pop)

            if self.cfg.use_nd_memory:
                nd_pool = merge_non_dominated(
                    nd_pool,
                    [(ind.objectives, ind) for ind in new_pop if ind.objectives is not None],
                    max_size=self.cfg.nd_pool_max,
                )
                ts_seed_pool = nd_pool
            else:
                ts_seed_pool = merge_non_dominated(
                    [],
                    [(ind.objectives, ind) for ind in new_pop if ind.objectives is not None],
                    max_size=self.cfg.nd_pool_max,
                )

            # TS component starts from sparse regions of the non-dominated pool.
            ts_pop: List[EncodedIndividual] = []
            if self.cfg.use_ts and ts_seed_pool:
                for seed_ind in self._select_ts_seeds(ts_seed_pool, self.cfg.tmax):
                    improved = self._tabu_search(seed_ind)
                    ev = evaluate_individual(self.instance, improved)
                    improved.objectives = ev.objectives
                    improved.feasible = ev.feasible
                    ts_pop.append(improved)
                if self.cfg.use_nd_memory:
                    nd_pool = merge_non_dominated(
                        nd_pool,
                        [(ind.objectives, ind) for ind in ts_pop if ind.objectives is not None],
                        max_size=self.cfg.nd_pool_max,
                    )

            # Environmental selection back to popsize.
            all_pop = new_pop + ts_pop
            objs = [ind.objectives for ind in all_pop]  # type: ignore[list-item]
            fronts = fast_non_dominated_sort(objs)  # type: ignore[arg-type]
            next_pop: List[EncodedIndividual] = []
            for front in fronts:
                if len(next_pop) + len(front) <= self.cfg.popsize:
                    next_pop.extend(all_pop[i] for i in front)
                else:
                    dist = crowding_distance(objs, front)  # type: ignore[arg-type]
                    pairs = sorted(zip(front, dist), key=lambda x: x[1], reverse=True)
                    next_pop.extend(all_pop[i] for i, _ in pairs[: self.cfg.popsize - len(next_pop)])
                    break
            pop = next_pop

            if not self.cfg.use_nd_memory:
                nd_pool = merge_non_dominated(
                    [],
                    [(ind.objectives, ind) for ind in pop if ind.objectives is not None],
                    max_size=self.cfg.nd_pool_max,
                )
            best_cost = min(ind.objectives[0] for ind in pop if ind.objectives is not None)
            best_mk = min(ind.objectives[1] for ind in pop if ind.objectives is not None)
            history.append({"iter": it, "best_cost": best_cost, "best_makespan": best_mk, "nd_size": len(nd_pool)})

        trace_file = str(self._trace_file) if self._trace_file is not None else None
        return RunResult(nd_solutions=[x[1] for x in nd_pool], history=history, trace_file=trace_file)
