> Current project rule: cross-chain penalty adds fixed cross-chain cost only; `cross_chain_cost_rate` is kept for compatibility and is always 0. Historical variable-cost notes below are superseded.

# EDA-TS 复现说明文档（算法对齐增强版，2026-05-11）

## 1. 结论

- 结论：当前 EDA-TS 已完成本轮算法层面的三项关键对齐：
  1. `PMA/PMS/PMM` 采样与更新按论文 Eq. (17)-(29)、Algorithm 1/2 改为累积概率矩阵口径；
  2. TS 短期 tabu 收敛为论文描述的邻域 II 口径，长期记忆 LMLS/LMLM 改为仅对“差于当前解”的 N1/N3 候选施加惩罚；
  3. 非支配解记忆池改为 EDA 后更新一次、TS 后再更新一次，再用于下一代 EDA 采样。
- 判定：EDA-TS 已从“主框架一致 + 关键细节近似”提升为“核心概率模型、TS 记忆机制、ND 记忆时序基本按论文对齐”。仍需注意，论文部分细节来自图示和文字描述，不是可执行伪代码，因此仍建议保留 trace 与测试证据链，而不表述为“源码级逐行完全相同”。

## 2. 本轮完成项

### 2.1 PMA/PMS/PMM 对齐（已完成）

- UA 采样：由直接 `np.choice` 改为 PMA 累积概率阈值采样，对齐 SPA 思路。
- OS 采样：按 Algorithm 1 使用 SPS 累积矩阵、剩余位置 POS 与随机阈值生成 OS 层。
- MS 采样：按 Algorithm 2 使用 SPM 累积矩阵与随机阈值选择机器。
- PMM 更新：按 Eq. (26)-(27) 修正无观测分支；当某个 `(job, op, sru)` 在 EN 中没有被分配到该 SRU 时，保持原 PMM 分布，而不是向零频次漂移。
- 测试证据：
  - `test_pmm_update_keeps_previous_distribution_when_assignment_unobserved`
  - `test_trace_snapshot_output`

### 2.2 TS tabu 与长期记忆对齐（已完成）

- 短期 tabu：
  - 旧逻辑：N1/N2/N3 都构造 move-level tabu key。
  - 新逻辑：仅邻域 II（OS 插入）进入短期 T list，对齐论文“T list based on neighborhood structure II”的描述。
  - T list 长度改为 `sum(min(5, Kx))`，对应论文 NII。
- 长期记忆：
  - N1 使用 `LMLS[(to_sru, job_id)]` 记录作业重分配频次。
  - N3 使用 `LMLM[(sru_id, job_id, op_id, to_machine)]` 记录机器选择频次。
  - 仅当候选邻域解被当前解支配时施加长期记忆惩罚，对齐论文“worse than current solution”触发语义。
- 测试证据：
  - `test_short_tabu_key_is_neighborhood_ii_only`

### 2.3 非支配解记忆池时序对齐（已完成）

- 旧逻辑：生成 EDA 新种群、追加 TS 解、环境选择后统一更新 ND pool。
- 新逻辑：
  1. EDA 新种群生成并评价后，先更新 ND pool；
  2. 从当前 ND pool 中选择 TS 初始解；
  3. TS 执行完成后，再用 TS 改进解更新 ND pool；
  4. 下一代概率矩阵更新时使用当前 ND pool 与 elite 共同构成 EN。
- 该流程对齐论文 Section 4.5/4.6 对 EDA、TS 与非支配解记忆机制交互的描述。

## 3. 当前仍需保留的审计边界

1. 多种群比例仍按当前工程配置固化为 UA `0.8/0.2`、MS `0.6/0.2/0.2`，其依据来自论文 Fig. 4，但图示比例仍建议在最终报告中单独引用说明。
2. 邻域规模 `min(5, ...)` 已按论文口径保留，但随机抽取顺序、并列解排序、拥挤距离截断等工程细节仍会影响随机轨迹。
3. 尚未生成“论文步骤号 -> 代码字段 -> 运行 trace”的自动对拍报告。

## 4. 当前准确表述建议

- 可以表述：**“EDA-TS 的概率模型、TS 短/长期记忆机制与非支配解记忆时序已按论文核心描述完成对齐。”**
- 谨慎表述：**“由于论文部分细节以图示和文字说明给出，当前实现仍需依赖 trace、测试和实验指标验证其算法级一致性。”**

## 5. 验证

- 命令：`$env:PYTHONPATH='src'; python -m unittest discover -s tests -p "test_*.py" -v`
- 当前结果：`Ran 11 tests, OK`
