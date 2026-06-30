from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from smdfjsp.core.types import Operation, ScheduleRecord


ObjVector = Tuple[float, ...]


@dataclass
class MVCJob:
    """MVC job with fixed value-chain and service-type labels."""

    job_id: int
    type_id: int
    type_label: str
    value_chain_id: str
    operations: List[Operation]
    candidate_sru_ids: List[int] = field(default_factory=list)
    release_time: float = 0.0


@dataclass
class MVCSRU:
    """Service resource unit in one value chain."""

    sru_id: int
    type_id: int
    type_label: str
    value_chain_id: str
    machine_ids: List[int]
    service_type_ids: List[int] = field(default_factory=list)
    service_type_labels: List[str] = field(default_factory=list)
    open_to_cross_chain: bool = True
    capacity: Optional[float] = None


@dataclass
class MVCModeConfig:
    """Experiment mode for the two-objective MVC-SM-DFJSP experiments."""

    cross_chain_allowed: bool = True
    objective_dim: int = 2

    def __post_init__(self) -> None:
        if self.objective_dim != 2:
            raise ValueError("MVC-SM-DFJSP formal experiments use objective_dim=2")


@dataclass
class MVCSMDFJSPInstance:
    """MVC-SM-DFJSP instance used by MVC-specific evaluators/algorithms."""

    name: str
    num_types: int
    jobs: List[MVCJob]
    srus: List[MVCSRU]
    transport_time: Dict[Tuple[int, int], float]
    transport_cost: Dict[Tuple[int, int], float]
    cross_chain_fixed_cost: Dict[Tuple[int, int], float]
    cross_chain_cost_rate: Dict[Tuple[int, int], float]
    is_cross_chain: Dict[Tuple[int, int], bool]
    metadata: Dict[str, object] = field(default_factory=dict)

    @property
    def num_jobs(self) -> int:
        return len(self.jobs)

    @property
    def num_srus(self) -> int:
        return len(self.srus)

    def job_map(self) -> Dict[int, MVCJob]:
        return {j.job_id: j for j in self.jobs}

    def sru_map(self) -> Dict[int, MVCSRU]:
        return {s.sru_id: s for s in self.srus}

    def jobs_by_type(self) -> Dict[int, List[MVCJob]]:
        grouped: Dict[int, List[MVCJob]] = {}
        for job in self.jobs:
            grouped.setdefault(job.type_id, []).append(job)
        return grouped

    def srus_by_type(self) -> Dict[int, List[MVCSRU]]:
        grouped: Dict[int, List[MVCSRU]] = {}
        for sru in self.srus:
            grouped.setdefault(sru.type_id, []).append(sru)
        return grouped


@dataclass
class MVCEvalResult:
    objectives: ObjVector
    feasible: bool
    records: List[ScheduleRecord]
    total_cost: float
    makespan: float
    max_sru_load: float
    cost_breakdown: Dict[str, float] = field(default_factory=dict)
    sru_loads: Dict[int, float] = field(default_factory=dict)
    diagnostics: Dict[str, object] = field(default_factory=dict)
    message: str = ""
