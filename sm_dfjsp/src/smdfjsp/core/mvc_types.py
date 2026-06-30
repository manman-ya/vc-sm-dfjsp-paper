"""MVC-SM-DFJSP 的核心数据结构定义。

这个文件可以按“数据表 schema”理解：`MVCJob` 描述订单/工件，
`MVCSRU` 描述服务资源单元，`MVCSMDFJSPInstance` 把订单、资源、
运输时间/成本、跨链成本等参数组织成一个完整算例。

价值链归属的关键字段是 `value_chain_id`：
- 订单的 `value_chain_id` 表示该订单原本属于哪条价值链。
- SRU 的 `value_chain_id` 表示该服务资源单元归属于哪条价值链。
- 后续候选资源判断、跨链固定成本、跨链流量统计都围绕这两个字段展开。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from smdfjsp.core.types import Operation, ScheduleRecord


ObjVector = Tuple[float, ...]


@dataclass
class MVCJob:
    """订单/工件记录。

    一个 `MVCJob` 对应需要被调度的一张订单。订单有固定的服务类型
    (`type_id`/`type_label`) 和固定价值链归属 (`value_chain_id`)。
    算法只能把订单分配给“能提供同类服务”的 SRU；是否允许跨价值链分配
    由 `MVCModeConfig.cross_chain_allowed` 控制。
    """

    # 订单唯一编号。编码层 UA/OS/OP/MS 都通过 job_id 引用订单。
    job_id: int
    # 服务类型的整数编号，用于快速比较候选 SRU 是否能加工该订单。
    type_id: int
    # 服务类型的原始标签，通常来自输入 JSON，例如某类加工/服务名称。
    type_label: str
    # 订单所属价值链。它和 SRU.value_chain_id 是否相等决定链内/跨链。
    value_chain_id: str
    # 订单包含的工序序列，每道工序有若干可选的 SRU/机器/加工时间/成本。
    operations: List[Operation]
    # 输入数据中显式给出的候选 SRU 标签转换结果；正式候选仍由 mvc_io 按模式过滤。
    candidate_sru_ids: List[int] = field(default_factory=list)
    # 订单释放时间；评价器调度第一道工序时不能早于该时间。
    release_time: float = 0.0


@dataclass
class MVCSRU:
    """服务资源单元记录。

    SRU 是可被订单选择的共享制造/服务资源单元。一个 SRU 只归属于一条
    价值链，但在 `open_to_cross_chain=True` 且实验模式允许跨链时，
    其他价值链的同服务类型订单也可以选择它。
    """

    # SRU 唯一编号。UA 层的取值就是这些 sru_id。
    sru_id: int
    # SRU 的主服务类型编号；目前基础模型中通常一个 SRU 对应一个服务类型。
    type_id: int
    # 服务类型原始标签，保留给导入导出和结果解释。
    type_label: str
    # SRU 所属价值链。与订单 value_chain_id 比较后决定是否跨链。
    value_chain_id: str
    # SRU 内部可用机器编号集合；MS 层会在这些机器中选择。
    machine_ids: List[int]
    # SRU 能服务的类型集合；候选过滤以这个集合为准，而不是只看 type_id。
    service_type_ids: List[int] = field(default_factory=list)
    # 服务类型标签集合，主要用于解释和导出。
    service_type_labels: List[str] = field(default_factory=list)
    # 是否开放给跨链订单。当前 validate_mvc_instance 要求基础模型全部开放。
    open_to_cross_chain: bool = True
    # 可选容量字段，当前评价器不直接使用，保留给扩展约束。
    capacity: Optional[float] = None


@dataclass
class MVCModeConfig:
    """实验模式配置。

    当前正式实验固定为双目标：`(total_cost, makespan)`。模式中最重要的
    开关是 `cross_chain_allowed`：关闭后，候选 SRU 只保留同价值链同类型资源。
    """

    # True 表示候选资源包含链内 + 跨链；False 表示只允许链内。
    cross_chain_allowed: bool = True
    # 正式模型只有两个目标：总成本和最大完工时间。
    objective_dim: int = 2

    def __post_init__(self) -> None:
        if self.objective_dim != 2:
            raise ValueError("MVC-SM-DFJSP formal experiments use objective_dim=2")


@dataclass
class MVCSMDFJSPInstance:
    """一个完整 MVC-SM-DFJSP 算例。

    这里把静态输入数据集中到一个对象中：订单表、SRU 表、运输时间/成本表、
    跨链固定成本表和跨链标记表。评价器只读取这些字段，不在这里保存调度结果。
    """

    # 算例名称，通常来自输入 JSON 的 instance_name。
    name: str
    # 服务类型数量。
    num_types: int
    # 订单集合。
    jobs: List[MVCJob]
    # SRU 集合。
    srus: List[MVCSRU]
    # (job_id, sru_id) -> 运输时间。完工时间目标会把它加到订单加工完成时间后。
    transport_time: Dict[Tuple[int, int], float]
    # (job_id, sru_id) -> 运输成本。总成本目标的第二部分。
    transport_cost: Dict[Tuple[int, int], float]
    # (job_id, sru_id) -> 跨链固定成本。只有跨链分配时计入 total_cost。
    cross_chain_fixed_cost: Dict[Tuple[int, int], float]
    # (job_id, sru_id) -> 跨链成本率元数据。正式双目标暂未计入，仅保留数据。
    cross_chain_cost_rate: Dict[Tuple[int, int], float]
    # (job_id, sru_id) -> 是否跨链。缺省时评价器会用价值链 id 是否相等推断。
    is_cross_chain: Dict[Tuple[int, int], bool]
    # 原始输入、标签映射等附加信息，方便复现和导出。
    metadata: Dict[str, object] = field(default_factory=dict)

    @property
    def num_jobs(self) -> int:
        return len(self.jobs)

    @property
    def num_srus(self) -> int:
        return len(self.srus)

    def job_map(self) -> Dict[int, MVCJob]:
        """按 job_id 建立订单索引，避免评价器反复线性查找。"""

        return {j.job_id: j for j in self.jobs}

    def sru_map(self) -> Dict[int, MVCSRU]:
        """按 sru_id 建立 SRU 索引，供候选判断、评价和统计使用。"""

        return {s.sru_id: s for s in self.srus}

    def jobs_by_type(self) -> Dict[int, List[MVCJob]]:
        """按服务类型分组订单。

        OS 层是按 `type_id` 分层编码的，因此概率模型和随机 OS 生成都需要这个分组。
        """

        grouped: Dict[int, List[MVCJob]] = {}
        for job in self.jobs:
            grouped.setdefault(job.type_id, []).append(job)
        return grouped

    def srus_by_type(self) -> Dict[int, List[MVCSRU]]:
        """按服务类型分组 SRU，主要用于分析和扩展。"""

        grouped: Dict[int, List[MVCSRU]] = {}
        for sru in self.srus:
            grouped.setdefault(sru.type_id, []).append(sru)
        return grouped


@dataclass
class MVCEvalResult:
    """单个编码个体的评价结果。

    `objectives` 是算法真正用于 Pareto 排序的目标向量；其余字段用于解释
    成本构成、资源负载和跨链流向，不改变正式目标函数。
    """

    # 正式目标向量，当前固定为 (total_cost, makespan)，两个目标都越小越好。
    objectives: ObjVector
    # 是否为可行调度；不可行解通常返回 inf 目标值。
    feasible: bool
    # 详细排程记录，每条记录对应一道工序在某 SRU/机器上的起止时间。
    records: List[ScheduleRecord]
    # 总成本 = processing_cost + transport_cost + cross_fixed_cost。
    total_cost: float
    # 最大完工时间 = 所有订单“加工完成时间 + 运输时间”的最大值。
    makespan: float
    # 最大 SRU 加工负载，用于诊断，不是正式目标。
    max_sru_load: float
    # 成本拆分，便于画图和论文结果分析。
    cost_breakdown: Dict[str, float] = field(default_factory=dict)
    # 每个 SRU 的加工负载。
    sru_loads: Dict[int, float] = field(default_factory=dict)
    # 跨链数量、流向、负载标准差等诊断信息。
    diagnostics: Dict[str, object] = field(default_factory=dict)
    # 不可行或异常时的说明信息。
    message: str = ""
