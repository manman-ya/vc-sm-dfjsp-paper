from __future__ import annotations

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
    popsize: int = 50
    max_iter: int = 100
    time_limit_s: float = 100.0
    alpha: float = 0.5  # PMA lr
    beta: float = 0.5  # PMS lr
    gamma: float = 0.5  # PMM lr
    mu: float = 0.1  # elite rate
    epsilon: float = 0.008  # penalty factor
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
    nd_solutions: List[EncodedIndividual]
    history: List[Dict[str, float]]
    trace_file: Optional[str] = None


class EDATS:
    def __init__(self, instance: SMDFJSPInstance, config: EDATSConfig):
        self.instance = instance
        self.cfg = config
        self.rng: RNGPack = make_rng(config.seed)
        self.option_index = build_option_index(instance)
        self.job_map = instance.job_map()
        self.sru_map = instance.sru_map()
        self.jobs_by_type = instance.jobs_by_type()
        self.srus_by_type = instance.srus_by_type()
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
        return EncodedIndividual(
            ua=dict(ind.ua),
            os={k: list(v) for k, v in ind.os.items()},
            op={k: list(v) for k, v in ind.op.items()},
            ms={k: list(v) for k, v in ind.ms.items()},
            aux=dict(ind.aux),
        )

    @staticmethod
    def _entropy(values: np.ndarray) -> float:
        if values.size == 0:
            return 0.0
        arr = values.astype(float)
        arr = arr[arr > 0.0]
        if arr.size == 0:
            return 0.0
        return float(-(arr * np.log(arr)).sum())

    def _trace_snapshot(self, it: int, en_size: int, nd_size: int) -> None:
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
        ua: Dict[int, int] = {}
        for t, jobs in self.jobs_by_type.items():
            for j in jobs:
                sru_ids = self.pma_srus[j.job_id]
                probs = self.pma[t][j.job_id]
                ua[j.job_id] = int(self.rng.np_rng.choice(sru_ids, p=probs))
        return ua

    def _md_ua(self) -> Dict[int, int]:
        ua: Dict[int, int] = {}
        for job in self.instance.jobs:
            candidates = self.compatible_srus.get(job.job_id, [])
            if not candidates:
                candidates = [s.sru_id for s in self.srus_by_type[job.type_id]]
            best = min(candidates, key=lambda sid: self.instance.transport_time[(job.job_id, sid)])
            ua[job.job_id] = best
        return ua

    def _sample_os(self) -> Dict[int, List[int]]:
        os_layer: Dict[int, List[int]] = {}
        for t, jobs in self.jobs_by_type.items():
            kx = self.kx[t]
            vec = [-1] * kx
            positions = list(range(kx))
            self.rng.py_rng.shuffle(positions)
            # Implement algorithm-1 style by weighted placement.
            for j in jobs:
                remain = len(j.operations)
                for _ in range(remain):
                    probs = self.pms[t][j.job_id]
                    if not positions:
                        break
                    pos_weights = np.array([probs[p] for p in positions], dtype=float)
                    if pos_weights.sum() <= 0:
                        idx = self.rng.py_rng.randrange(len(positions))
                    else:
                        pos_weights = pos_weights / pos_weights.sum()
                        idx = int(self.rng.np_rng.choice(np.arange(len(positions)), p=pos_weights))
                    pos = positions.pop(idx)
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
        ms: Dict[int, List[int]] = {}
        for sru_id, seq in op_layer.items():
            vec: List[int] = []
            for job_id, op_id in seq:
                key = (job_id, op_id, sru_id)
                machines = self.pmm_machines.get(key)
                probs = self.pmm.get(key)
                if machines and probs is not None:
                    vec.append(int(self.rng.np_rng.choice(machines, p=probs)))
                    continue
                options = self.option_index.get(key, {})
                if options:
                    vec.append(int(self.rng.py_rng.choice(list(options.keys()))))
            ms[sru_id] = vec
        return ms

    def _mc_ms(self, op_layer: Dict[int, List[Tuple[int, int]]]) -> Dict[int, List[int]]:
        """Choose machine with minimum processing completion cost (pt * cp)."""
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
        """Greedy choose machine to minimize projected completion time."""
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
        for ind in pop:
            result = evaluate_individual(instance, ind)
            ind.objectives = result.objectives
            ind.feasible = result.feasible

    def _select_elite(self, pop: List[EncodedIndividual], elite_size: int) -> List[EncodedIndividual]:
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

    def _update_probability_matrices(self, en: List[EncodedIndividual]) -> None:
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
            for ind in en:
                sru_id = key[2]
                seq = ind.op.get(sru_id, [])
                ms_vec = ind.ms.get(sru_id, [])
                for i, item in enumerate(seq):
                    if item == (key[0], key[1]) and i < len(ms_vec):
                        m = ms_vec[i]
                        if m in mpos:
                            freq[mpos[m]] += 1.0
            if freq.sum() > 0:
                freq /= freq.sum()
            self.pmm[key] = (1.0 - self.cfg.gamma) * base + self.cfg.gamma * freq
            if self.pmm[key].sum() <= 0:
                self.pmm[key] = np.ones(len(base)) / len(base)
            else:
                self.pmm[key] /= self.pmm[key].sum()

    def _neighbor_structure_i(self, ind: EncodedIndividual) -> List[EncodedIndividual]:
        """Job re-assignment among same-type SRUs."""
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
        """Insert move in OS."""
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
        """Machine replacement in MS."""
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
        return (obj[0] + self.cfg.epsilon * obj[0] * freq, obj[1] + self.cfg.epsilon * obj[1] * freq)

    @staticmethod
    def _build_tabu_key(ind: EncodedIndividual) -> Tuple:
        mk = str(ind.aux.get("move_kind", ""))
        if mk == "N1":
            return ("N1", int(ind.aux["job_id"]), int(ind.aux["to_sru"]))
        if mk == "N2":
            return (
                "N2",
                int(ind.aux["type_id"]),
                int(ind.aux["job_id"]),
                int(ind.aux["from_pos"]),
                int(ind.aux["to_pos"]),
            )
        if mk == "N3":
            return (
                "N3",
                int(ind.aux["sru_id"]),
                int(ind.aux["job_id"]),
                int(ind.aux["op_id"]),
                int(ind.aux["to_machine"]),
            )
        # Fallback key for safety.
        return tuple(ind.os[t][0] if ind.os[t] else -1 for t in sorted(ind.os))

    def _tabu_search(self, initial: EncodedIndividual) -> EncodedIndividual:
        current = initial
        current_eval = evaluate_individual(self.instance, current)
        current.objectives = current_eval.objectives
        best = current
        best_obj = current.objectives

        t_list: List[Tuple] = []
        lmls: Dict[Tuple[int, int], int] = {}
        lmlm: Dict[Tuple[int, int, int, int], int] = {}
        t_max_len = max(5, sum(min(5, self.kx[t]) for t in self.kx))

        for _ in range(max(1, self.cfg.tmax)):
            n1 = self._neighbor_structure_i(current)
            n2 = self._neighbor_structure_ii(current)
            n3 = self._neighbor_structure_iii(current)
            neighbors = n1 + n2 + n3
            if not neighbors:
                break
            self._evaluate_population(self.instance, neighbors)

            scored: List[Tuple[ObjPair, EncodedIndividual]] = []
            for nb in neighbors:
                obj = nb.objectives  # type: ignore[assignment]
                pen = 0
                mk = str(nb.aux.get("move_kind", ""))
                if mk == "N1":
                    pen += lmls.get((int(nb.aux["to_sru"]), int(nb.aux["job_id"])), 0)
                elif mk == "N3":
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
            scored.sort(key=lambda x: (x[0][0], x[0][1]))
            chosen = None
            for _, cand in scored:
                tabu_key = self._build_tabu_key(cand)
                # Aspiration criterion: allow tabu move if it improves current best.
                improves_best = dominates(cand.objectives, best_obj)  # type: ignore[arg-type]
                if tabu_key not in t_list or improves_best:
                    chosen = cand
                    t_list.append(tabu_key)
                    if len(t_list) > t_max_len:
                        t_list.pop(0)
                    break
            if chosen is None:
                chosen = scored[0][1]
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
        return best

    def run(self) -> RunResult:
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
            if (time.time() - start) >= self.cfg.time_limit_s:
                break
            elite_size = max(1, int(self.cfg.mu * self.cfg.popsize))
            elites = self._select_elite(pop, elite_size)
            en = elites + ([x[1] for x in nd_pool] if self.cfg.use_nd_memory else [])
            self._update_probability_matrices(en)
            self._trace_snapshot(it=it, en_size=len(en), nd_size=len(nd_pool))

            new_pop = [self._build_individual() for _ in range(self.cfg.popsize)]
            self._evaluate_population(self.instance, new_pop)

            # TS component starts Tmax times.
            if self.cfg.use_ts and nd_pool:
                for _ in range(self.cfg.tmax):
                    seed_ind = self.rng.py_rng.choice(nd_pool)[1]
                    improved = self._tabu_search(seed_ind)
                    ev = evaluate_individual(self.instance, improved)
                    improved.objectives = ev.objectives
                    improved.feasible = ev.feasible
                    new_pop.append(improved)

            # Environmental selection back to popsize.
            all_pop = new_pop
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

            if self.cfg.use_nd_memory:
                nd_pool = merge_non_dominated(
                    nd_pool,
                    [(ind.objectives, ind) for ind in pop if ind.objectives is not None],
                    max_size=self.cfg.nd_pool_max,
                )
            else:
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
