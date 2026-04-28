# EDA-TS 复现说明文档（代码已完成三项优先改造版）

## 1. 结论
- 结论：**当前 EDA-TS 仍不是“与论文完全一致”**，但已经完成三项优先改造：
  1. `tabu_key`：从 OS 头 token 改为 move 级键；
  2. `LMLS/LMLM`：改为按邻域动作类型触发；
  3. `PMA/PMS/PMM trace`：已支持迭代级审计快照输出。
- 判定：由“主框架一致 + 关键细节近似”提升为“主框架一致 + 关键机制可审计增强”，但仍未达到论文逐行同构。

## 2. 本轮改造完成项（你要求的 3 点）

### 2.1 tabu_key 改造（已完成）
- 旧逻辑：`tabu_key = tuple(cand.os[t][0] ...)`（OS 头 token）。
- 新逻辑：基于 move 语义构造 key（N1/N2/N3）：
  - N1: `("N1", job_id, to_sru)`
  - N2: `("N2", type_id, job_id, from_pos, to_pos)`
  - N3: `("N3", sru_id, job_id, op_id, to_machine)`
- 代码证据：
  - 新增 key 构造函数：`algorithm.py:483`
  - tabu 使用与 aspiration：`algorithm.py:551`
  - move 元信息写入：
    - N1：`algorithm.py:406`
    - N2：`algorithm.py:436`
    - N3：`algorithm.py:468`

### 2.2 LMLS/LMLM 触发逻辑改造（已完成）
- 旧逻辑：对“候选个体相对 current 的全量差异”聚合惩罚，触发粒度偏粗。
- 新逻辑：按邻域动作类型触发记忆：
  - N1 候选仅查询/更新 `LMLS[(to_sru, job_id)]`
  - N3 候选仅查询/更新 `LMLM[(sru_id, job_id, op_id, to_machine)]`
  - N2 不触发长期频次记忆惩罚
- 代码证据：
  - 频次容器定义：`algorithm.py:514`、`algorithm.py:515`
  - 惩罚读取（按 move_kind）：`algorithm.py:532`、`algorithm.py:534`
  - 频次更新（按 move_kind）：`algorithm.py:561`、`algorithm.py:564`

### 2.3 PMA/PMS/PMM trace 审计输出（已完成）
- 新增配置项：
  - `trace_enabled`：开关
  - `trace_dir`：输出目录
  - `trace_every`：采样间隔
- 新增输出：
  - 每代审计快照（jsonl），包含：
    - PMA/PMS/PMM 的完整概率向量
    - 各矩阵熵均值（便于观察收敛）
    - `iter`、`en_size`、`nd_size` 等运行上下文
- 代码证据：
  - 配置项：`algorithm.py:42`
  - trace 文件初始化：`algorithm.py:67`
  - trace 快照函数：`algorithm.py:93`
  - 迭代中写快照：`algorithm.py:599`
  - 结果返回 trace 文件路径：`algorithm.py:645`

## 3. 目前仍与论文不一致的点（改造后仍存在）

### 3.1 PMA/PMS/PMM 仍非“论文伪代码逐行同构”
- 当前仍是工程化概率更新流程，虽可审计，但并非论文步骤号逐行复刻。
- 证据：`algorithm.py:323`（更新主流程）

### 3.2 多种群比例仍为固定工程参数
- UA `0.8/0.2`，MS `0.6/0.2/0.2` 固化在分支逻辑。
- 证据：`algorithm.py:283`、`algorithm.py:288`

### 3.3 邻域采样规模仍为固定上限 `min(5, ...)`
- 证据：
  - N1：`algorithm.py:393`
  - N2：`algorithm.py:421`
  - N3：`algorithm.py:454`

### 3.4 缺少“论文步骤号级”自动对拍报告
- 已有 trace，但尚未实现“步骤号 -> 统计指标 -> 一致性判定”自动报告。

## 4. 为什么仍未完全一致
1. 当前代码目标仍偏“可运行 + 可审计 + 可复现实验”，不是“逐行伪代码复刻器”。
2. 论文文本对部分实现细则（尤其禁忌键编码）没有完全工程化定义，仍需解释性映射。
3. 现阶段只优先改了你指定三项，尚未全面重写所有 EDA/TS 微观步骤。

## 5. 当前准确表述建议
- 可以表述：**“EDA-TS 主框架复现完成，且 tabu_key、长期记忆触发、概率矩阵 trace 审计能力已增强。”**
- 不应表述：**“EDA-TS 已与论文逐行完全一致。”**

## 6. 如何启用新的 trace 审计
在 `EDATSConfig` 中设置：
1. `trace_enabled=True`
2. `trace_dir='reports/repro/trace'`
3. `trace_every=1`

运行后可在 `trace_dir` 下获得 `edats_trace_seed*.jsonl`，并在 `RunResult.trace_file` 中取到文件路径。
