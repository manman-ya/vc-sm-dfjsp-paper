from __future__ import annotations

import math
from typing import Iterable, List, Sequence, Tuple


ObjVector = Tuple[float, ...]


def dominates(a: Sequence[float], b: Sequence[float]) -> bool:
    if len(a) != len(b):
        raise ValueError("Objective vectors must have the same dimension")
    return all(x <= y for x, y in zip(a, b)) and any(x < y for x, y in zip(a, b))


def fast_non_dominated_sort(objs: Sequence[Sequence[float]]) -> List[List[int]]:
    n = len(objs)
    if n == 0:
        return []
    dominated_by_count = [0] * n
    dominates_set: List[List[int]] = [[] for _ in range(n)]
    fronts: List[List[int]] = [[]]
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            if dominates(objs[i], objs[j]):
                dominates_set[i].append(j)
            elif dominates(objs[j], objs[i]):
                dominated_by_count[i] += 1
        if dominated_by_count[i] == 0:
            fronts[0].append(i)
    f = 0
    while f < len(fronts) and fronts[f]:
        nxt: List[int] = []
        for i in fronts[f]:
            for j in dominates_set[i]:
                dominated_by_count[j] -= 1
                if dominated_by_count[j] == 0:
                    nxt.append(j)
        if nxt:
            fronts.append(nxt)
        f += 1
    return fronts


def get_non_dominated_indices(objs: Sequence[Sequence[float]]) -> List[int]:
    fronts = fast_non_dominated_sort(objs)
    return fronts[0] if fronts else []


def filter_non_dominated(objs: Sequence[ObjVector]) -> List[ObjVector]:
    return [objs[i] for i in get_non_dominated_indices(objs)]


def crowding_distance(objs: Sequence[Sequence[float]], front: Sequence[int]) -> List[float]:
    if not front:
        return []
    if len(front) <= 2:
        return [float("inf")] * len(front)
    dim = len(objs[0])
    dist = [0.0] * len(front)
    pos = {idx: i for i, idx in enumerate(front)}
    for d in range(dim):
        ordered = sorted(front, key=lambda idx: objs[idx][d])
        dist[pos[ordered[0]]] = float("inf")
        dist[pos[ordered[-1]]] = float("inf")
        lo = float(objs[ordered[0]][d])
        hi = float(objs[ordered[-1]][d])
        if hi == lo:
            continue
        for k in range(1, len(ordered) - 1):
            prev_v = float(objs[ordered[k - 1]][d])
            next_v = float(objs[ordered[k + 1]][d])
            dist[pos[ordered[k]]] += (next_v - prev_v) / (hi - lo)
    return dist


def merge_non_dominated(
    base: Iterable[Tuple[ObjVector, object]],
    incoming: Iterable[Tuple[ObjVector, object]],
    max_size: int | None = None,
) -> List[Tuple[ObjVector, object]]:
    merged = list(base) + list(incoming)
    if not merged:
        return []
    seen = set()
    unique: List[Tuple[ObjVector, object]] = []
    for obj, item in merged:
        key = tuple(round(float(x), 10) for x in obj)
        if key in seen:
            continue
        seen.add(key)
        unique.append((tuple(float(x) for x in obj), item))
    nd = [unique[i] for i in get_non_dominated_indices([x[0] for x in unique])]
    if max_size is not None and len(nd) > max_size:
        objs = [x[0] for x in nd]
        front = list(range(len(nd)))
        distances = crowding_distance(objs, front)
        ranked = sorted(zip(nd, distances), key=lambda x: x[1], reverse=True)
        nd = [x[0] for x in ranked[:max_size]]
    return nd


def euclidean(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        raise ValueError("Objective vectors must have the same dimension")
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def gd(front: Sequence[Sequence[float]], reference: Sequence[Sequence[float]]) -> float:
    if not front or not reference:
        return float("inf")
    return math.sqrt(sum(min(euclidean(a, r) for r in reference) ** 2 for a in front)) / len(front)


def raw_igd(front: Sequence[Sequence[float]], reference: Sequence[Sequence[float]]) -> float:
    """Return IGD in the original objective units."""
    if not front or not reference:
        return float("inf")
    return sum(min(euclidean(r, a) for a in front) for r in reference) / len(reference)


def c_metric(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> float:
    if not b:
        return 0.0
    return sum(1 for bb in b if any(dominates(aa, bb) for aa in a)) / len(b)


def spacing(front: Sequence[Sequence[float]]) -> float:
    if len(front) <= 1:
        return 0.0
    nearest = []
    for i, point in enumerate(front):
        nearest.append(min(euclidean(point, other) for j, other in enumerate(front) if i != j))
    mean_d = sum(nearest) / len(nearest)
    return math.sqrt(sum((d - mean_d) ** 2 for d in nearest) / max(len(nearest) - 1, 1))


def build_reference_front(fronts: Sequence[Sequence[Sequence[float]]]) -> List[ObjVector]:
    union = [tuple(float(x) for x in point) for front in fronts for point in front]
    if not union:
        return []
    return filter_non_dominated(union)


def auto_reference_point(fronts: Sequence[Sequence[Sequence[float]]], margin_ratio: float = 0.1) -> ObjVector:
    points = [tuple(float(x) for x in point) for front in fronts for point in front]
    if not points:
        raise ValueError("Cannot build a reference point from empty fronts")
    dim = len(points[0])
    maxs = [max(p[d] for p in points) for d in range(dim)]
    mins = [min(p[d] for p in points) for d in range(dim)]
    return tuple(maxs[d] + max(maxs[d] - mins[d], 1.0) * margin_ratio for d in range(dim))


def objective_bounds(fronts: Sequence[Sequence[Sequence[float]]]) -> Tuple[ObjVector, ObjVector]:
    points = [tuple(float(x) for x in point) for front in fronts for point in front]
    if not points:
        raise ValueError("Cannot build objective bounds from empty fronts")
    dim = len(points[0])
    mins = tuple(min(p[d] for p in points) for d in range(dim))
    maxs = tuple(max(p[d] for p in points) for d in range(dim))
    return mins, maxs


def normalize_front(
    front: Sequence[Sequence[float]],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
) -> List[ObjVector]:
    if len(lower_bounds) != len(upper_bounds):
        raise ValueError("Bounds must have the same dimension")
    spans = [max(float(upper_bounds[d]) - float(lower_bounds[d]), 1.0) for d in range(len(lower_bounds))]
    return [
        tuple((float(point[d]) - float(lower_bounds[d])) / spans[d] for d in range(len(spans)))
        for point in front
    ]


def normalized_igd(
    front: Sequence[Sequence[float]],
    reference: Sequence[Sequence[float]],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
) -> float:
    """Return dimensionless IGD after shared min-max normalization."""
    if not front or not reference:
        return float("inf")
    norm_front = normalize_front(front, lower_bounds, upper_bounds)
    norm_reference = normalize_front(reference, lower_bounds, upper_bounds)
    return raw_igd(norm_front, norm_reference)


def igd(
    front: Sequence[Sequence[float]],
    reference: Sequence[Sequence[float]],
    lower_bounds: Sequence[float] | None = None,
    upper_bounds: Sequence[float] | None = None,
) -> float:
    """Return normalized IGD; derive shared bounds when they are omitted.

    Batch experiment code should pass bounds shared by every front for the same
    problem instance. Automatic bounds are intended for standalone comparisons.
    Use :func:`raw_igd` only when the original objective-space distance is
    explicitly required for auditing.
    """
    if not front or not reference:
        return float("inf")
    if (lower_bounds is None) != (upper_bounds is None):
        raise ValueError("Both lower_bounds and upper_bounds must be provided together")
    if lower_bounds is None or upper_bounds is None:
        lower_bounds, upper_bounds = objective_bounds([front, reference])
    return normalized_igd(front, reference, lower_bounds, upper_bounds)


def normalized_reference_point(
    reference_point: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
) -> ObjVector:
    if len(reference_point) != len(lower_bounds) or len(lower_bounds) != len(upper_bounds):
        raise ValueError("Reference point and bounds must have the same dimension")
    spans = [max(float(upper_bounds[d]) - float(lower_bounds[d]), 1.0) for d in range(len(lower_bounds))]
    return tuple((float(reference_point[d]) - float(lower_bounds[d])) / spans[d] for d in range(len(spans)))


def normalized_hypervolume(
    front: Sequence[Sequence[float]],
    reference_point: Sequence[float],
    lower_bounds: Sequence[float],
    upper_bounds: Sequence[float],
) -> float:
    """Return minimization HV normalized by the reference hyper-rectangle volume.

    The objective values and reference point are first min-max normalized using
    a shared set of bounds. The resulting hypervolume is divided by the volume
    of the normalized rectangle from the ideal point at zero to the normalized
    reference point, so comparable fronts have a dimensionless HV in [0, 1].
    """
    if not front:
        return 0.0
    norm_front = normalize_front(front, lower_bounds, upper_bounds)
    norm_ref = normalized_reference_point(reference_point, lower_bounds, upper_bounds)
    denominator = 1.0
    for value in norm_ref:
        denominator *= max(float(value), 1e-12)
    if denominator <= 0.0:
        return 0.0
    return float(hypervolume(norm_front, norm_ref) / denominator)


def hypervolume_2d(front: Sequence[Sequence[float]], reference_point: Sequence[float]) -> float:
    if len(reference_point) != 2:
        raise ValueError("2D hypervolume requires a 2D reference point")
    if not front:
        return 0.0
    nd = filter_non_dominated([tuple(float(x) for x in p) for p in front])
    ordered = sorted(nd, key=lambda p: p[0])
    hv = 0.0
    prev_y = float(reference_point[1])
    ref_x = float(reference_point[0])
    for x, y in ordered:
        width = max(ref_x - float(x), 0.0)
        height = max(prev_y - float(y), 0.0)
        hv += width * height
        prev_y = min(prev_y, float(y))
    return float(hv)


def hypervolume_3d(front: Sequence[Sequence[float]], reference_point: Sequence[float]) -> float:
    if len(reference_point) != 3:
        raise ValueError("3D hypervolume requires a 3D reference point")
    if not front:
        return 0.0
    nd = sorted(filter_non_dominated([tuple(float(x) for x in p) for p in front]), key=lambda p: p[0])
    hv = 0.0
    prev_x = float(reference_point[0])
    # Sweep from high x to low x; each slice contributes a 2D HV in y-z.
    for point in sorted(nd, key=lambda p: p[0], reverse=True):
        width = max(prev_x - point[0], 0.0)
        yz_front = [(p[1], p[2]) for p in nd if p[0] <= point[0]]
        hv += width * hypervolume_2d(yz_front, (reference_point[1], reference_point[2]))
        prev_x = point[0]
    return float(hv)


def hypervolume(front: Sequence[Sequence[float]], reference_point: Sequence[float]) -> float:
    if len(reference_point) == 2:
        return hypervolume_2d(front, reference_point)
    if len(reference_point) == 3:
        return hypervolume_3d(front, reference_point)
    raise NotImplementedError("Hypervolume is implemented for 2D and 3D only")
