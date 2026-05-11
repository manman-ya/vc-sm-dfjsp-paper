# SM-DFJSP EDA-TS 算法映射文档

## 1. 范围
- 论文算法范围：EDA-TS，包括 PMA/PMS/PMM、多种群策略、TS 三类邻域、短期/长期记忆禁忌机制、非支配记忆机制。
- 代码基线：
  - `src/smdfjsp/eda_ts/algorithm.py`
  - `src/smdfjsp/baselines/*.py`（对比算法）

## 2. 状态说明
- `same`：机制意图已实现，基本一致。
- `approx`：机制意图已实现，但过程细节与论文伪代码存在差异。
- `missing`：未发现显式实现。

## 3. EDA-TS 步骤映射

| 论文组件 | 代码证据 | 状态 | 说明 |
|---|---|---|---|
| 四层编码（UA/OS/OP/MS） | `core/encoding.py:106`, `core/encoding.py:175` | `same` | 已有完整编码与修复流程。 |
| PMA/PMS/PMM 概率矩阵 | `algorithm.py` | `same` | 三类概率矩阵显式初始化。 |
| PMA/PMS/PMM 采样 | `algorithm.py` | `same` | UA/MS 改为累积概率阈值采样，OS 按 Algorithm 1 的 SPS/POS 阈值逻辑生成。 |
| 代际多种群策略 | `algorithm.py` | `same` | UA: sampling/MD；MS: sampling/MC/MCT。 |
| PMA/PMS/PMM 更新 | `algorithm.py` | `same` | 按 Eq. (18)/(22)/(26)-(27) 的 EN 频次与学习率更新；PMM 无观测时保持原分布。 |
| TS 邻域 I（作业重分配） | `algorithm.py` | `same` | 已实现基于兼容集合的 SRU 迁移。 |
| TS 邻域 II（OS 插入） | `algorithm.py` | `same` | 已实现 OS 序列插入操作。 |
| TS 邻域 III（MS 替换） | `algorithm.py` | `same` | 已实现工序机器替换。 |
| 短期禁忌表 | `algorithm.py` | `same` | 已收敛为邻域 II 专用 T list，长度为 `sum(min(5, Kx))`，并保留 aspiration 逻辑。 |
| 长期记忆惩罚（LMLS/LMLM） | `algorithm.py` | `same` | N1 使用 LMLS、N3 使用 LMLM，且仅当候选解差于当前解时施加惩罚。 |
| 非支配记忆池 | `algorithm.py` | `same` | 已按 EDA 后更新、TS 后再更新、下一代参与 EN 的时序实现。 |
| EDA/TS 协同迭代 | `algorithm.py` | `same` | 已实现 EDA 生成 + ND pool 更新 + TS 局部强化 + ND pool 再更新。 |
| 终止条件（max_iter/time_limit） | `algorithm.py` | `same` | 两类终止条件均已实现。 |
| PMA/PMS/PMM 审计追踪 | `algorithm.py` | `same` | 已支持 `trace_enabled/trace_dir/trace_every` 的迭代快照输出（jsonl）。 |

## 4. 对比算法映射

| 论文对比算法 | 代码证据 | 状态 | 说明 |
|---|---|---|---|
| EDA | `baselines/eda.py` | `approx` | 通过关闭 TS/多种群/ND 记忆获得的工程变体。 |
| NSGA-II | `baselines/nsgaii.py` | `approx` | 功能实现存在，但未完成文献算子级同构审计。 |
| EDA-VNS | `baselines/eda.py`（`run_eda_vns`） | `approx` | 作为统一框架下配置化变体实现。 |
| H-GA-TS | `baselines/h_gats.py` | `approx` | GA 主干 + TS 辅助的工程等价实现。 |

## 5. 严格复现差距
1. 论文部分细节依赖图示和文字说明，仍建议补充“论文步骤号 -> 代码输出字段”的自动对拍报告。
2. 多种群比例来自论文 Fig. 4，当前按工程固定比例实现，最终报告中应单独说明。
3. 对比算法需要独立完成参数/算子与原始文献的一致性审计。

## 6. 建议补充的可审计能力
1. 在现有 trace 基础上，补充邻域接受/拒绝率、tabu 命中率统计。
2. 增加“论文步骤号 -> 代码输出字段”的自动对拍报告。
3. 保留确定性种子回归测试（`tests/` 已具备）用于防漂移。
