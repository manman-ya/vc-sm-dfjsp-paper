from __future__ import annotations

from copy import deepcopy
from typing import Dict, List, Tuple

from smdfjsp.core.encoding import build_option_index, op_from_ua_os, repair_ms, repair_os
from smdfjsp.core.mvc_types import MVCModeConfig, MVCSMDFJSPInstance
from smdfjsp.core.random_utils import RNGPack
from smdfjsp.core.types import EncodedIndividual
from smdfjsp.data.mvc_io import get_candidate_srus


def build_mvc_compatible_sru_map(
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
) -> Dict[int, List[int]]:
    option_index = build_option_index(instance)  # type: ignore[arg-type]
    compatible: Dict[int, List[int]] = {}
    for job in instance.jobs:
        candidates: List[int] = []
        for sid in get_candidate_srus(job, instance, mode):
            ok = all((job.job_id, op.op_id, sid) in option_index for op in job.operations)
            if ok:
                candidates.append(sid)
        compatible[job.job_id] = candidates
    return compatible


def random_mvc_ua(
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
) -> Dict[int, int]:
    compatible = build_mvc_compatible_sru_map(instance, mode)
    ua: Dict[int, int] = {}
    for job in instance.jobs:
        candidates = compatible.get(job.job_id, [])
        if not candidates:
            raise ValueError(f"Job {job.job_id} has no feasible SRU under mode={mode}")
        ua[job.job_id] = int(rng.py_rng.choice(candidates))
    return ua


def repair_mvc_individual(
    individual: EncodedIndividual,
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
) -> EncodedIndividual:
    fixed = deepcopy(individual)
    option_index = build_option_index(instance)  # type: ignore[arg-type]
    compatible = build_mvc_compatible_sru_map(instance, mode)
    for job in instance.jobs:
        sid = fixed.ua.get(job.job_id)
        if sid not in compatible.get(job.job_id, []):
            candidates = compatible.get(job.job_id, [])
            if not candidates:
                raise ValueError(f"Job {job.job_id} has no feasible SRU under mode={mode}")
            fixed.ua[job.job_id] = int(rng.py_rng.choice(candidates))

    fixed.os = repair_os(instance, fixed.os, rng)  # type: ignore[arg-type]
    fixed.op = op_from_ua_os(instance, fixed.ua, fixed.os)  # type: ignore[arg-type]
    fixed.ms = repair_ms(instance, fixed.op, fixed.ms, option_index, rng)  # type: ignore[arg-type]
    return fixed


def build_random_mvc_individual(
    instance: MVCSMDFJSPInstance,
    mode: MVCModeConfig,
    rng: RNGPack,
) -> EncodedIndividual:
    from smdfjsp.core.encoding import random_ms, random_os

    option_index = build_option_index(instance)  # type: ignore[arg-type]
    ua = random_mvc_ua(instance, mode, rng)
    os_layer = random_os(instance, rng)  # type: ignore[arg-type]
    op_layer = op_from_ua_os(instance, ua, os_layer)  # type: ignore[arg-type]
    ms_layer = random_ms(instance, op_layer, option_index, rng)  # type: ignore[arg-type]
    return repair_mvc_individual(EncodedIndividual(ua=ua, os=os_layer, op=op_layer, ms=ms_layer), instance, mode, rng)


def best_machine_ms(
    instance: MVCSMDFJSPInstance,
    op_layer: Dict[int, List[Tuple[int, int]]],
    key: str,
) -> Dict[int, List[int]]:
    option_index = build_option_index(instance)  # type: ignore[arg-type]
    ms: Dict[int, List[int]] = {}
    for sru_id, seq in op_layer.items():
        vec: List[int] = []
        for job_id, op_id in seq:
            options = option_index[(job_id, op_id, sru_id)]
            if key == "time":
                chosen = min(options, key=lambda m: options[m][0])
            else:
                chosen = min(options, key=lambda m: options[m][0] * options[m][1])
            vec.append(int(chosen))
        ms[sru_id] = vec
    return ms

