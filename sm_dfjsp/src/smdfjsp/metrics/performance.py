from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple

import numpy as np

from smdfjsp.core.pareto import dominates, get_non_dominated_indices
from smdfjsp.core.types import ObjPair
from smdfjsp.metrics import multiobjective


def euclidean(a: ObjPair, b: ObjPair) -> float:
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2)


def build_pf_known(fronts: Sequence[Sequence[ObjPair]]) -> List[ObjPair]:
    union = [x for f in fronts for x in f]
    if not union:
        return []
    nd_idx = get_non_dominated_indices(union)
    return [union[i] for i in nd_idx]


def gd(pf_a: Sequence[ObjPair], pf_true: Sequence[ObjPair]) -> float:
    if not pf_a or not pf_true:
        return float("inf")
    d2 = []
    for a in pf_a:
        near = min(euclidean(a, t) for t in pf_true)
        d2.append(near**2)
    return float(math.sqrt(sum(d2)) / len(d2))


def raw_igd(pf_a: Sequence[ObjPair], pf_true: Sequence[ObjPair]) -> float:
    """Return IGD in the original two-objective units."""
    return multiobjective.raw_igd(pf_a, pf_true)


def normalized_igd(
    pf_a: Sequence[ObjPair],
    pf_true: Sequence[ObjPair],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
) -> float:
    """Return dimensionless IGD using shared objective bounds."""
    return multiobjective.normalized_igd(pf_a, pf_true, lower_bounds, upper_bounds)


def igd(
    pf_a: Sequence[ObjPair],
    pf_true: Sequence[ObjPair],
    lower_bounds: Sequence[float] | None = None,
    upper_bounds: Sequence[float] | None = None,
) -> float:
    """Return normalized IGD; automatic bounds support standalone callers."""
    return multiobjective.igd(pf_a, pf_true, lower_bounds, upper_bounds)


def c_metric(a: Sequence[ObjPair], b: Sequence[ObjPair]) -> float:
    if not b:
        return 0.0
    dominated = 0
    for bb in b:
        if any(dominates(aa, bb) for aa in a):
            dominated += 1
    return dominated / len(b)


def ods(front: Sequence[ObjPair]) -> float:
    """Objective deviation sum used in parameter design."""
    if not front:
        return float("inf")
    arr = np.array(front, dtype=float)
    mins = arr.min(axis=0)
    mins[mins == 0] = 1.0
    score = ((arr - mins) / mins).sum(axis=1).mean()
    return float(score)


def build_reference_front(fronts: Sequence[Sequence[Sequence[float]]]) -> List[Tuple[float, ...]]:
    """Build a non-dominated reference front for 2D/3D MVC experiments."""
    return multiobjective.build_reference_front(fronts)


def auto_reference_point(fronts: Sequence[Sequence[Sequence[float]]], margin_ratio: float = 0.1) -> Tuple[float, ...]:
    """Build a dominated reference point for hypervolume calculation."""
    return multiobjective.auto_reference_point(fronts, margin_ratio=margin_ratio)


def hypervolume(front: Sequence[Sequence[float]], reference_point: Sequence[float]) -> float:
    """Return 2D or 3D minimization hypervolume."""
    return multiobjective.hypervolume(front, reference_point)


def normalized_hypervolume(
    front: Sequence[Sequence[float]],
    reference_point: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
) -> float:
    """Return dimensionless minimization hypervolume in [0, 1]."""
    return multiobjective.normalized_hypervolume(front, reference_point, lower_bounds, upper_bounds)


def spacing(front: Sequence[Sequence[float]]) -> float:
    """Return spacing for an arbitrary-dimensional objective front."""
    return multiobjective.spacing(front)


def spread(front: Sequence[Sequence[float]]) -> float:
    """Alias kept for paper tables that call the diversity metric spread."""
    return multiobjective.spacing(front)

