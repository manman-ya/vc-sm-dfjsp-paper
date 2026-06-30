from __future__ import annotations

"""非支配档案。

MVC-EDA-TS 是多目标算法，目标通常是成本和最大完工时间。
非支配档案保存历史搜索过程中发现的 Pareto 非支配解：
- 作为最终输出的近似 Pareto 前沿；
- 作为概率模型学习集的一部分，避免只学习当前代短期趋势；
- 作为局部搜索起点，强化前沿稀疏区域。
"""

from dataclasses import dataclass, field
from typing import List, Tuple

from smdfjsp.core.types import EncodedIndividual
from smdfjsp.metrics.multiobjective import merge_non_dominated


@dataclass
class NonDominatedArchive:
    """固定容量的 Pareto 非支配解集合。"""

    max_size: int = 300
    # items 中每个元素是 (目标向量, 个体)。目标向量越小越好。
    items: List[Tuple[Tuple[float, ...], EncodedIndividual]] = field(default_factory=list)

    def update(self, population: List[EncodedIndividual]) -> None:
        """把一批已评价个体合并进档案。

        `merge_non_dominated` 会删除被支配解；超过容量时按拥挤距离等规则保留多样性。
        未评价个体没有 objectives，不能进入档案。
        """

        incoming = [(tuple(ind.objectives or ()), ind) for ind in population if ind.objectives is not None]
        self.items = merge_non_dominated(self.items, incoming, max_size=self.max_size)

    def solutions(self) -> List[EncodedIndividual]:
        """仅返回档案中的个体，隐藏内部保存的目标向量。"""

        return [item for _, item in self.items]
