"""MVC-EDA-TS 算法包的公开入口。

外部脚本通常只需要导入 `MVCEDATS` 和 `MVCEDATSConfig`：
- `MVCEDATSConfig` 配置种群规模、迭代次数、局部搜索开关等参数。
- `MVCEDATS` 执行完整的概率模型采样 + MVC 局部搜索流程。
"""

from smdfjsp.mvc_eda_ts.algorithm import MVCEDATS, MVCEDATSConfig

__all__ = ["MVCEDATS", "MVCEDATSConfig"]
