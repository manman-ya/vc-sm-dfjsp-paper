# SM-DFJSP 模型公式映射文档

## 1. 范围
- 论文：*Shared manufacturing-based distributed flexible job shop scheduling with supply-demand matching*（C&IE 189, 2024, 109950）。
- 目标：将论文模型部分公式（Eq. (1)-(16)）映射到当前代码实现。
- 当前代码基线：
  - `src/smdfjsp/model/evaluator.py`
  - `src/smdfjsp/model/gurobi_model.py`
  - `src/smdfjsp/core/encoding.py`

## 2. 状态说明
- `same`：优化意图已直接实现，基本一致。
- `approx`：优化意图已实现，但变量体系或符号形式为工程等价实现，并非逐符号一一同构。
- `missing`：未发现严格对应论文公式形式的闭环实现。

## 3. Eq. (1)-(16) 映射

| 论文公式 | 论文意图（摘要） | 代码证据 | 状态 | 说明 |
|---|---|---|---|---|
| Eq. (1) | 最小化总成本 `C` | `gurobi_model.py:114`, `gurobi_model.py:136`, `evaluator.py:61-94` | `same` | 成本由加工成本与运输成本组成并计算。 |
| Eq. (2) | 最小化完工期 `MK` | `gurobi_model.py:129`, `gurobi_model.py:137`, `evaluator.py:82-95` | `same` | 双目标优化意图保留。 |
| Eq. (3) | 作业到 SRU 的唯一分配 | `gurobi_model.py:70` | `approx` | 以 `sum_s A[j,s] == 1` 实现。 |
| Eq. (4) | 工序机器/SRU 唯一选择 | `gurobi_model.py:75` | `approx` | 以 `sum_{s,m} B[j,o,s,m] == 1` 实现。 |
| Eq. (5) | 工序分配与作业-SRU 分配联动 | `gurobi_model.py:79` | `approx` | 通过 `B <= A` 联动约束实现。 |
| Eq. (6) | 工序完成时间定义 | `gurobi_model.py:84` | `approx` | 通过 `E = S + processing_time`（基于 `B`）实现。 |
| Eq. (7) | 作业内工序先后约束 | `gurobi_model.py:92` | `approx` | 已实现相邻工序时序约束。 |
| Eq. (8) | 作业完成时间定义 | `gurobi_model.py:93` | `approx` | 以 `F[j] >= E[last_op]` 实现。 |
| Eq. (9) | 机器不重叠约束 | `gurobi_model.py:102`, `gurobi_model.py:107` | `approx` | 采用 Big-M 成对析取约束。 |
| Eq. (10) | 成本聚合约束 | `gurobi_model.py:114` | `same` | 显式聚合加工与运输成本。 |
| Eq. (11) | 含运输的完工期下界 | `gurobi_model.py:129` | `same` | 以 `MK >= F[j] + transport_time` 实现。 |
| Eq. (12) | 二元变量域约束 | `gurobi_model.py` 变量声明 | `approx` | `A/B/Y` 为二元变量，但未与论文符号逐条文档化。 |
| Eq. (13) | 时间变量非负约束 | `gurobi_model.py` 变量声明 | `approx` | `S/E/F/C/MK` 下界为 `0`。 |
| Eq. (14) | 供需类型一致性约束 | `core/encoding.py:175`, `evaluator.py:85-87` | `approx` | 通过修复与运行时检查保证，不是独立 MILP 符号块。 |
| Eq. (15) | 工序可行选项约束 | `core/encoding.py:13-166`, `evaluator.py:50-60` | `approx` | 基于 option index 保证可行，不是论文符号一一对应。 |
| Eq. (16) | 额外边界/域约束 | 未发现同名显式方程块 | `missing` | 需补充论文符号级审计与映射。 |

## 4. 差距总结
- 当前模型已复现目标函数意图与核心调度可行性约束。
- 但尚未达到“公式符号逐项同构”：
  - 论文变量体系（如 `A/B/...`）尚未形成逐项符号字典映射。
  - 缺少按公式编号组织的可执行证明性产物（逐式校验）。

## 5. 下一步（严格复现）
1. 新增 `模型符号字典`：论文符号 -> 代码变量/函数 -> 单位/定义域。
2. 按约束类别补充公式级可执行单测（unit tests）。
3. 新增按 Eq. ID 输出模型审计日志的脚本，用于求解过程核对。
