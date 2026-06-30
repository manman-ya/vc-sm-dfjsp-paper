# MVC-SM-DFJSP 双目标项目修改实施方案与清单

创建日期：2026-06-07
依据文档：`sm_dfjsp/docs/MVC_SM_DFJSP_双目标论文方法实现文档_2026-06-07.md`
执行状态：已按用户确认范围执行

## 1. 改造目标

本次改造的目标不是重写项目，而是把当前代码、脚本、测试和实验输出统一到论文方法文档确定的双目标口径：

```text
min F1 = total_cost = processing_cost + transport_cost + cross_fixed_cost
min F2 = makespan
```

`max_sru_load`、`sru_load_std`、`cross_chain_ratio`、`value_chain_inflow`、`value_chain_outflow`、`cross_chain_flow` 等只作为诊断和管理启示指标，不作为主实验优化目标。

## 2. 当前项目初步判断

已具备的能力：

1. `src/smdfjsp/model/mvc_evaluator.py` 已按固定跨链成本计算 `total_cost`，且 `cross_variable_cost` 保持为 0 的兼容字段。
2. `src/smdfjsp/core/mvc_types.py` 中 `MVCModeConfig` 默认 `objective_dim=2`。
3. `src/smdfjsp/mvc_eda_ts/probability_model.py` 已实现价值链先验概率模型，包含加工成本、运输成本、固定跨链成本、完成时间估计和跨链时间收益。
4. `src/smdfjsp/mvc_eda_ts/tabu_search.py` 已有 6 类邻域及邻域贡献统计。
5. `scripts/run_mvc_experiments.py`、`scripts/run_mvc_ablation.py`、`scripts/run_mvc_sensitivity.py` 已有主实验、消融和敏感性实验入口。
6. `tests/test_mvc_evaluator.py` 已覆盖固定跨链成本口径。

需要修改或收口的风险点：

1. 主实验和消融脚本默认 `objective_dim=3`，与双目标论文主线冲突。
2. 初始化策略尚未完整显式覆盖文档中的 5 类策略，且没有记录 `ind.aux["init_strategy"]`。
3. 实验输出对 `value_chain_inflow`、`value_chain_outflow`、`cross_chain_flow`、成本拆分和邻域贡献统计的汇总还不够论文友好。
4. 消融实验变体需要对齐 A0-A5：`w/o VC init`、`w/o VC prior`、`w/o cross neighborhoods`、`w/o adaptive neighborhood`、`w/o ND memory`。
5. 现有 3 目标兼容路径可以保留，但必须在默认参数、脚本说明和测试中明确为兼容/扩展能力，避免主实验误用。

## 3. 修改步骤

### Step 0：执行前基线确认

目的：确认当前代码可测试、关键脚本可导入，并记录修改前状态。

拟执行：

```text
python -m pytest tests/test_mvc_evaluator.py tests/test_mvc_eda_ts.py tests/test_mvc_algorithms.py
python scripts/run_mvc_experiments.py --max-instances 1 --popsize 6 --max-iter 1 --time-limit 5 --objective-dim 2
python scripts/run_mvc_ablation.py --popsize 6 --max-iter 1 --time-limit 5 --objective-dim 2
```

通过标准：

1. 关键 MVC 单元测试通过。
2. 主实验和消融脚本能在小规模参数下产出 CSV。
3. 若失败，先记录失败原因，再决定是否进入修复。

### Step 1：固化双目标默认口径

涉及文件：

```text
src/smdfjsp/core/mvc_types.py
scripts/run_mvc_experiments.py
scripts/run_mvc_ablation.py
scripts/run_mvc_sensitivity.py
scripts/mvc_experiment_utils.py
tests/test_mvc_experiment_scripts.py
tests/test_mvc_algorithms.py
```

实现方案：

1. 将主实验、消融、敏感性脚本默认 `--objective-dim` 统一改为 `2`。
2. 保留 `objective_dim=3` 的兼容能力，但在脚本帮助文本和 `run_meta.json` 中标明三目标为扩展/诊断模式。
3. 检查所有实验汇总列：主排序、折中解、指标汇总默认只使用 `total_cost` 和 `makespan`。
4. 保留 `max_sru_load` 输出列，但不进入主目标指标，除非显式传入 `--objective-dim 3`。

验收标准：

1. 不传 `--objective-dim` 时，所有 MVC 实验脚本输出 `objective_dim=2`。
2. `metrics_summary.csv` 的 HV/IGD/GD/Spacing 默认基于两维目标。
3. 原有 3 目标测试仍可通过，作为兼容测试。

### Step 2：成本口径与数据一致性审计

涉及文件：

```text
src/smdfjsp/model/mvc_evaluator.py
src/smdfjsp/data/mvc_io.py
scripts/validate_mvc_instances.py
scripts/build_mvc_mk01_15.py
scripts/build_mk01_15_2vc_equalproc_vcpenalty.py
tests/test_mvc_evaluator.py
tests/test_mvc_io.py
```

实现方案：

1. 增强验证脚本，检查正式数据集中 `cross_chain_cost_rate == 0`，链内 `cross_chain_fixed_cost == 0`。
2. 在验证输出中增加成本口径说明：`total_cost = processing_cost + transport_cost + cross_fixed_cost`。
3. 增加测试，确认跨链开/关模式下候选 SRU 与固定成本统计一致。
4. 保留 `cross_chain_cost_rate` 字段作为历史兼容字段，但不参与目标函数。

验收标准：

1. `validate_mvc_instances.py` 可报告固定跨链成本口径。
2. `test_total_cost_uses_fixed_cross_cost_only` 继续通过。
3. 正式 MVC-MK 数据集中不存在非零 `cross_chain_cost_rate`。

### Step 3：补齐价值链感知初始化策略

涉及文件：

```text
src/smdfjsp/mvc_eda_ts/initialization.py
src/smdfjsp/mvc_eda_ts/algorithm.py
src/smdfjsp/mvc_eda_ts/probability_model.py
tests/test_mvc_eda_ts.py
```

实现方案：

1. 将初始化策略统一命名为：

```text
random
intra-chain-first
cost-first
time-first
cross-gain-first
```

2. 在 `build_heuristic_individual` 中实现 `cross-gain-first`：优先选择跨链时间收益明显且成本可接受的 SRU。
3. 在每个初始化个体的 `ind.aux["init_strategy"]` 中记录策略名称。
4. 在 `MVCEDATS._initial_population()` 中按混合策略生成初始种群，保证至少覆盖低成本链内、低工期跨链和随机探索三类解。
5. 若 `cross_chain_allowed=False`，自动禁用 `cross-gain-first` 或退化为 `intra-chain-first`/`time-first`。

验收标准：

1. 初始种群中能看到 `init_strategy` 记录。
2. `cross_chain_allowed=False` 时不会生成跨链 UA。
3. `cross_chain_allowed=True` 且存在跨链候选时，初始化能产生一定比例跨链方案。

### Step 4：收口价值链先验概率模型

涉及文件：

```text
src/smdfjsp/mvc_eda_ts/probability_model.py
src/smdfjsp/mvc_eda_ts/algorithm.py
tests/test_mvc_eda_ts.py
```

实现方案：

1. 保留当前评分公式和权重，作为论文文档默认实现。
2. 将 `prior_temperature`、`prior_weight` 与配置项关系梳理清楚，必要时暴露到 `MVCEDATSConfig`。
3. 增加轻量测试，验证 `use_value_chain_prior=False` 时 `pua` 为可行候选上的均匀/学习概率，而不是强行使用先验。
4. 可选：在调试输出或 history 中增加先验启用标志，便于消融追踪。

验收标准：

1. `no_prior` 消融能真正关闭价值链先验。
2. 先验概率对每个订单归一化，且不会包含不可行 SRU。

### Step 5：确认跨链禁忌邻域与消融开关

涉及文件：

```text
src/smdfjsp/mvc_eda_ts/tabu_search.py
src/smdfjsp/mvc_eda_ts/algorithm.py
scripts/run_mvc_ablation.py
tests/test_mvc_eda_ts.py
```

实现方案：

1. 保留 6 类邻域：

```text
N1_intra_sru_replace
N2_cross_sru_replace
N3_cross_return
N4_critical_cross_migration
N5_high_cost_return
N6_machine_or_os_local
```

2. 检查 `use_cross_chain_neighbors=False` 时是否只启用 N1 和 N6。
3. 检查 `cross_chain_allowed=False` 时 N2/N4 不产生跨链候选。
4. 保留自适应邻域贡献统计，并在 history 中输出 `nh_prob_*`、`nh_reward_*`、`nh_accepted_*`。
5. 清理或说明 `use_bottleneck_release` 等历史配置名，避免它与跨链邻域语义混淆。

验收标准：

1. 跨链关闭模式下，局部搜索不会引入跨链 UA。
2. 消融 `no_cross_neighbors` 不再生成 N2-N5。
3. history 中可以看到邻域贡献统计，支持论文“邻域贡献”分析。

### Step 6：统一主实验与消融实验脚本

涉及文件：

```text
scripts/run_mvc_experiments.py
scripts/run_mvc_ablation.py
scripts/run_mvc_sensitivity.py
scripts/mvc_experiment_utils.py
configs/repro/*.yaml
```

实现方案：

1. 主实验默认：

```text
input-dir = data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty
algorithms = nsgaii,moead,mvc-edats
cross-modes = off,on
objective-dim = 2
```

2. 消融实验默认映射为 A0-A5：

```text
A0 full
A1 no_vc_init
A2 no_prior
A3 no_cross_neighbors
A4 no_adaptive_neighborhood
A5 no_archive
```

3. 保留额外变体 `no_probability_model`、`no_critical_migration` 等作为扩展，不放入默认正式消融。
4. 输出 `run_meta.json`，记录算法、模式、种子、目标维度、配置覆盖项。
5. 视需要增加 `--variant-set official|extended`，默认 `official`。

验收标准：

1. 主实验不传参即可按双目标口径跑 smoke。
2. 消融默认只跑 A0-A5，且输出中包含 `variant_code`。
3. 输出 CSV 能直接用于表 3、表 4、表 5。

### Step 7：增强实验输出与论文表图输入

涉及文件：

```text
scripts/mvc_experiment_utils.py
scripts/build_mvc_tables.py
scripts/build_mvc_figures.py
src/smdfjsp/visualization/mvc_plots.py
```

实现方案：

1. 在 `front_rows()` 中补充诊断字段：

```text
cross_chain_flow
value_chain_inflow
value_chain_outflow
value_chain_load_std
processing_cost
transport_cost
cross_fixed_cost
total_cost
```

2. `summarize_metrics()` 增加：

```text
mean_total_cost
mean_makespan
mean_cross_chain_ratio
mean_cross_fixed_cost
mean_transport_cost
mean_sru_load_std
```

3. 表构建脚本输出：

```text
table_algorithm_performance.csv
table_ablation.csv
table_cross_chain_analysis.csv
table_cost_breakdown.csv
```

4. 图构建脚本输出：

```text
pareto_fronts.png
cross_chain_flow.png
sru_load_distribution.png
convergence_curves.png
neighborhood_contribution.png
```

验收标准：

1. 论文需要的主表和图可以由 CSV/PNG 直接生成。
2. 成本拆分、跨链比例、跨链流动和负载分布都有可追踪来源。

### Step 8：测试与回归验证

拟运行：

```text
python -m pytest tests/test_mvc_evaluator.py tests/test_mvc_io.py tests/test_mvc_repair.py tests/test_mvc_eda_ts.py tests/test_mvc_algorithms.py tests/test_mvc_experiment_scripts.py
python scripts/validate_mvc_instances.py --input-dir data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty --max-instances 2
python scripts/run_mvc_experiments.py --max-instances 1 --popsize 6 --max-iter 1 --time-limit 5
python scripts/run_mvc_ablation.py --popsize 6 --max-iter 1 --time-limit 5
python scripts/run_mvc_sensitivity.py --popsize 6 --max-iter 1 --time-limit 5
```

验收标准：

1. 关键测试通过。
2. 三类实验脚本 smoke 运行成功。
3. 输出目标维度默认为 2。
4. 所有正式结果文件中 `cross_variable_cost` 为兼容列，不参与 `total_cost`。

## 4. 实施优先级

### P0：必须完成

1. 主实验、消融、敏感性脚本默认双目标。
2. 固定成本口径验证与测试。
3. 初始化策略补齐并记录 `init_strategy`。
4. A0-A5 消融变体对齐论文文档。
5. smoke 测试通过。

### P1：建议完成

1. 输出 `value_chain_inflow/outflow/cross_chain_flow`。
2. 生成论文表格 CSV。
3. 生成 Pareto、流动、负载、邻域贡献图。
4. history 增加更清晰的邻域贡献记录。

### P2：可延后

1. 进一步参数化先验权重。
2. 扩展 LA 实例泛化实验。
3. 统计检验和 10/20 次随机种子大规模运行。

## 5. 执行清单

确认后按以下清单推进：

- [ ] 备份并记录当前 `git status`。
- [ ] 跑 Step 0 基线测试。
- [ ] 修改脚本默认目标维度为 2。
- [ ] 增强 MVC 数据验证与成本口径测试。
- [ ] 实现并记录 5 类初始化策略。
- [ ] 检查价值链先验开关与概率归一化。
- [ ] 检查跨链禁忌邻域开关和 history 输出。
- [ ] 对齐 A0-A5 官方消融。
- [ ] 增强实验 CSV 诊断字段。
- [ ] 增强/生成表图构建脚本。
- [ ] 跑 MVC 单元测试。
- [ ] 跑主实验 smoke。
- [ ] 跑消融 smoke。
- [ ] 跑敏感性 smoke。
- [ ] 汇总修改文件、测试结果和剩余风险。

## 6. 待确认事项

执行前建议确认三点：

1. 主实验数据集是否采用 `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty` 作为默认正式数据集。
2. 三目标能力是否仅保留为兼容模式，不再进入正式主实验。
3. 是否同步生成论文表图脚本，还是本轮只完成代码口径和实验 CSV。

## 7. 默认执行建议

如果无额外要求，建议采用以下默认范围：

```text
默认数据集：data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty
正式目标：objective_dim=2
正式算法：nsgaii, moead, mvc-edats
正式模式：cross_chain off/on
正式消融：A0-A5
本轮执行范围：完成 P0 + P1 中的实验 CSV 输出增强
图表生成：先保证数据源和脚本接口，完整大规模图表等 smoke 通过后再跑
```

## 8. 执行结果记录

本轮已按确认范围完成：

- [x] 主实验默认数据集切换为 `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`。
- [x] 正式 MVC 入口只保留双目标 `objective_dim=2`。
- [x] `max_sru_load` 从正式优化目标中移除，仅作为诊断指标保留。
- [x] MVC-EDA-TS 初始化补齐并记录 `random`、`intra-chain-first`、`cost-first`、`time-first`、`cross-gain-first`。
- [x] 官方消融对齐 A0-A5。
- [x] 主实验、消融、敏感性实验输出增强成本拆分、跨链流动、价值链流入/流出、SRU 负载等字段。
- [x] 同步生成论文表格脚本和图脚本。

已验证：

```text
python -m pytest tests/test_mvc_evaluator.py tests/test_mvc_io.py tests/test_mvc_repair.py tests/test_mvc_eda_ts.py tests/test_mvc_algorithms.py tests/test_mvc_nsgaii.py tests/test_mvc_pareto.py tests/test_mvc_experiment_scripts.py
结果：17 passed

python scripts/validate_mvc_instances.py --input-dir data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty --out-dir reports/_tmp_test_trace/mvc_validation_new --max-instances 2
结果：validated: 2/2

python scripts/run_mvc_experiments.py --out-dir reports/_tmp_test_trace/mvc_experiments_new --max-instances 1 --popsize 6 --max-iter 1 --time-limit 5 --seeds 20260428
结果：成功生成主实验 Pareto、metrics、history 输出

python scripts/run_mvc_ablation.py --out-dir reports/_tmp_test_trace/mvc_ablation_new --popsize 6 --max-iter 1 --time-limit 5
结果：成功运行 A0-A5 官方消融

python scripts/run_mvc_sensitivity.py --out-dir reports/_tmp_test_trace/mvc_sensitivity_new --fixed-costs 0,20 --popsize 6 --max-iter 1 --time-limit 5
结果：成功生成敏感性实验输出

python scripts/build_mvc_tables.py --experiment-dir reports/_tmp_test_trace/mvc_experiments_new --ablation-dir reports/_tmp_test_trace/mvc_ablation_new --sensitivity-dir reports/_tmp_test_trace/mvc_sensitivity_new --out-dir reports/_tmp_test_trace/mvc_tables_new
结果：成功生成论文表格 CSV

python scripts/build_mvc_figures.py --experiment-dir reports/_tmp_test_trace/mvc_experiments_new --ablation-dir reports/_tmp_test_trace/mvc_ablation_new --sensitivity-dir reports/_tmp_test_trace/mvc_sensitivity_new --out-dir reports/_tmp_test_trace/mvc_figures_new
结果：成功生成论文图 PNG
```
