# MVC-SM-DFJSP 代码实现步骤与未实现清单

创建日期：2026-05-12  
最近更新：2026-05-28  
当前依据：`MVC_SM_DFJSP_两目标论文执行方案_2026-05-28.md`

本文档用于跟踪当前两目标论文路线的代码实现状态。2026-05-28 起，正式口径统一为：

```text
min F1 = total_cost = processing_cost + transport_cost + cross_fixed_cost
min F2 = makespan
```

`max_sru_load`、`sru_load_std`、`cross_chain_ratio`、`value_chain_inflow/outflow` 只作为辅助分析指标。`cross_variable_cost` 与 `cross_chain_cost_rate` 仅作为历史兼容字段保留，固定为 0，不参与目标函数和论文结果解释。

## 1. 当前原则

- 订单只能选择同服务类型 SRU。
- `cross_chain_allowed = false` 时，只允许本价值链同类型 SRU。
- `cross_chain_allowed = true` 时，允许跨价值链同类型 SRU。
- 所有 SRU 在基础数据中默认开放共享，跨链是否可用由实验模式控制。
- 正式论文主线只做两目标：成本与工期。
- 负载指标不作为优化目标，只用于结果诊断和管理启示。
- 新正式实验应使用统一固定成本口径后重跑的结果，历史 reports 仅作过程记录。

## 2. 已完成内容

### 2.1 MVC 数据结构与读取

- [x] `src/smdfjsp/core/mvc_types.py`
  - `MVCJob`
  - `MVCSRU`
  - `MVCSMDFJSPInstance`
  - `MVCEvalResult`
  - `MVCModeConfig`
- [x] `src/smdfjsp/data/mvc_io.py`
  - MVC JSON 读取与保存。
  - MVC 实例校验。
  - 链内/跨链候选 SRU 生成。
- [x] `src/smdfjsp/data/mvc_builder.py`
  - 通用 MVC-MK 数据构造器。
  - 固定跨链成本兼容字段 `cross_chain_cost_rate = 0`。

### 2.2 MVC 评价与修复

- [x] `src/smdfjsp/model/mvc_evaluator.py`
  - 二目标评价。
  - 成本拆分。
  - makespan 计算。
  - SRU 负载、价值链负载、跨链比例和跨链流向诊断。
  - 当前总成本为 `processing_cost + transport_cost + cross_fixed_cost`。
- [x] `src/smdfjsp/model/mvc_repair.py`
  - UA、OS、MS 可行性修复。
  - cross-off/cross-on 模式约束修复。

### 2.3 MVC-EDA-TS 增强版

- [x] `src/smdfjsp/mvc_eda_ts/algorithm.py`
  - 主循环、非支配档案、精英选择、TS 起点选择。
  - 自适应邻域概率更新。
  - history 输出邻域概率、reward、生成数和接受数。
- [x] `src/smdfjsp/mvc_eda_ts/probability_model.py`
  - PMA/PMS/PMM 概率模型。
  - 基于当前候选集合的采样。
  - 价值链感知 PMA 先验：加工成本、运输成本、固定跨链成本、预计完工时间、跨链工期收益。
- [x] `src/smdfjsp/mvc_eda_ts/initialization.py`
  - 启发式初始解。
- [x] `src/smdfjsp/mvc_eda_ts/tabu_search.py`
  - 显式六类邻域：链内替换、跨链替换、跨链回流、关键订单跨链迁移、高成本跨链回流、机器/OS 局部调整。
  - 候选按非支配排序和拥挤距离选择。
  - 按 `move_kind` 定义 tabu key，并统计生成、接受、archive 插入和目标改进。
- [x] `src/smdfjsp/mvc_eda_ts/archive.py`
  - 非支配解档案。

### 2.4 基准算法与指标

- [x] `src/smdfjsp/baselines/mvc_nsgaii.py`
- [x] `src/smdfjsp/baselines/mvc_moead.py`
- [x] `src/smdfjsp/baselines/mvc_edats_baseline.py`
- [x] `src/smdfjsp/metrics/multiobjective.py`
- [x] `src/smdfjsp/metrics/performance.py`
- [x] `src/smdfjsp/visualization/mvc_plots.py`

### 2.5 数据与脚本

- [x] `data/mvc_mk01_15/`
  - 历史 MVC-MK01 至 MVC-MK15 数据集。
- [x] `data/mvc_la/`
  - LA 扩展数据集，采用不同 SRU 加工时间/加工成本一致化原则。
- [x] `data/mvc_mk13_2vc4sru_fixedcost/`
  - 新增 MK13 两价值链、两类型、四 SRU、固定跨链成本数据。
  - 数据文件：`mk13_mvc_2vc_2type_4sru_equalproc_fixedcost.json`
- [x] `scripts/build_mk13_2vc_equalproc_fixedcost.py`
  - 生成新 MK13 固定成本数据。
- [x] `scripts/run_mvc_experiments.py`
- [x] `scripts/run_mvc_ablation.py`
- [x] `scripts/run_mvc_sensitivity.py`
- [x] `scripts/run_mvc_mk13_conflict_2obj_resumable.py`
- [x] `scripts/run_mvc_mk13_moead_50iter.py`
- [x] `scripts/run_mvc_la_all_compare.py`
- [x] `scripts/run_mvc_la_batch_edats_on_lbub.py`
- [x] `scripts/build_mvc_tables.py`
- [x] `scripts/build_mvc_figures.py`

### 2.6 测试

- [x] `tests/test_mvc_io.py`
- [x] `tests/test_mvc_evaluator.py`
- [x] `tests/test_mvc_repair.py`
- [x] `tests/test_mvc_pareto.py`
- [x] `tests/test_mvc_algorithms.py`
- [x] `tests/test_mvc_nsgaii.py`
- [x] `tests/test_mvc_eda_ts.py`
- [x] `tests/test_mvc_experiment_scripts.py`

最近验证：

```powershell
python sm_dfjsp\scripts\build_mk13_2vc_equalproc_fixedcost.py
python -m pytest sm_dfjsp\tests\test_mvc_evaluator.py sm_dfjsp\tests\test_mvc_io.py sm_dfjsp\tests\test_mvc_repair.py
python -m pytest sm_dfjsp\tests
python sm_dfjsp\scripts\run_mvc_single.py --input data/mvc_mk13_2vc4sru_fixedcost/mk13_mvc_2vc_2type_4sru_equalproc_fixedcost.json --out-dir reports/_tmp_test_trace/mk13_fixedcost_edats_smoke --algorithm mvc-edats --cross-chain on --objective-dim 2 --seed 20260528 --popsize 8 --max-iter 2 --time-limit 10
```

结果：MVC 针对性测试 `14 passed`；全量测试 `29 passed`；MK13 固定成本 smoke 输出 3 个 Pareto 点，history 中包含 6 类邻域概率字段。

## 3. 未实现与待加强清单

### 3.1 成本口径收尾

- [x] 修改 `mvc_evaluator.py`，总成本不再加入 `cross_variable_cost`。
- [x] 新 MK13 数据固定 `cross_chain_cost_rate = 0`。
- [ ] 更新 `data/mvc_mk01_15/README.md`，移除正式口径中的变动成本表述。
- [ ] 更新 `MVC_SM_DFJSP_论文初稿_2026-05-15.md` 的目标函数和成本说明。
- [ ] 更新 `MVC_SM_DFJSP_论文构造与整体实现新方案_2026-05-12.md` 中被新方案取代的成本段落。
- [x] 增加专门测试：断言 `total_cost == processing_cost + transport_cost + cross_fixed_cost`。

### 3.2 价值链感知 PMA

目标文件：`src/smdfjsp/mvc_eda_ts/probability_model.py`

- [x] 新增 `build_value_chain_prior()`。
- [x] 建立 `processing_cost`、`transport_cost`、`cross_fixed_cost`、预计完工时间、跨链工期收益的评分。
- [x] 新增 `prior_weight` 参数。
- [x] 在 `update()` 中融合 `P_prior` 和 `P_elite`。
- [x] 新增配置开关 `use_value_chain_prior`。
- [x] 在配置中保留 `prior_weight`，用于论文算法解释和消融。

### 3.3 显式跨链协同邻域

目标文件：`src/smdfjsp/mvc_eda_ts/tabu_search.py`

当前代码已按论文方案显式拆成六类：

- [x] `N1_intra_sru_replace`：链内 SRU 替换。
- [x] `N2_cross_sru_replace`：跨链 SRU 替换。
- [x] `N3_cross_return`：已跨链订单回流链内。
- [x] `N4_critical_cross_migration`：关键订单跨链迁移。
- [x] `N5_high_cost_return`：高成本跨链订单回流或低成本迁移。
- [x] `N6_machine_or_os_local`：机器替换、工序插入或局部重排。
- [x] 每个邻域写入稳定 `move_kind`。
- [x] tabu key 根据邻域类型分别定义。
- [x] 记录每类邻域生成数、接受数、进入 archive 数和目标改进。

### 3.4 自适应邻域选择

目标文件：`src/smdfjsp/mvc_eda_ts/algorithm.py`、`src/smdfjsp/mvc_eda_ts/tabu_search.py`

- [x] 新增邻域概率向量 `p = [p1, ..., p6]`。
- [x] 根据 accepted count、archive insert count、objective improvement 计算 reward。
- [x] 每代根据局部搜索统计更新邻域概率。
- [x] 在 `history` 中输出邻域概率、reward、生成数和接受数。
- [x] 新增 `use_adaptive_neighborhood` 配置开关。
- [ ] 图表脚本增加“邻域选择概率演化图”。

### 3.5 消融配置

目标文件：`scripts/run_mvc_ablation.py`、`scripts/mvc_experiment_utils.py`

- [x] `no_prior`
- [x] `no_cross_neighbors`
- [x] `no_critical_migration`
- [x] `no_adaptive_neighborhood`
- [x] `no_archive` 已有基础开关，可按新命名整理。
- [x] 每个消融版本输出统一元数据，便于表格脚本读取。

### 3.6 正式实验重跑

历史结果可保留，但正式论文应按固定成本口径重跑。

- [x] 用 `data/mvc_mk13_2vc4sru_fixedcost/` 先跑 smoke。
- [ ] MK05/MK13 小规模验证：NSGA-II、MOEA/D、EDA-TS baseline、MVC-EDA-TS。
- [ ] 主实验：MVC-MK01 至 MVC-MK15。
- [ ] 每算法每模式 20 次独立运行。
- [ ] 输出 HV、IGD、GD、Spacing、C-metric、front size、runtime、min cost、min makespan。
- [ ] 输出 Wilcoxon signed-rank test。
- [ ] 输出 Friedman average rank。

### 3.7 敏感性分析聚焦

目标：只保留论文方案中的三类敏感性。

- [ ] 跨链固定成本因子：`{0.5, 1.0, 1.5, 2.0}`。
- [ ] 运输成本因子：`{0.5, 1.0, 1.5, 2.0}`。
- [ ] 跨链资源速度优势：`weak / medium / strong`。
- [ ] 删除或降级历史 `cross_chain_cost_rate` 敏感性分析。

## 4. 推荐执行顺序

1. 更新旧 README 和论文初稿中的固定成本口径。
2. 图表脚本增加邻域概率演化图。
3. 跑 MK05/MK13 小规模正式验证。
4. 跑 MVC-MK01 至 MVC-MK15 正式实验。
5. 生成论文表格、图件和统计检验。
6. 回填论文初稿。

## 5. 当前验收标准

- [x] 同一订单链内和跨链都只能选择同类型 SRU。
- [x] cross-off 模式完全不产生跨链调用。
- [x] cross-on 模式允许同类型跨链调用。
- [x] 成本目标按固定跨链成本口径计算。
- [x] 新 MK13 两价值链四 SRU 数据已生成并通过校验。
- [x] 价值链感知 PMA 完成。
- [x] 六类跨链协同邻域完成。
- [x] 自适应邻域选择完成。
- [x] 新消融版本完成。
- [ ] 固定成本口径下正式实验完成。

## 6. 变更记录

```text
2026-05-12:
- 创建初版实现清单。
- 建立 MVC 类型、loader、evaluator、NSGA-II、MVC-EDA-TS 初版和单实例脚本。

2026-05-13:
- 完成 MVC-MK01-15 数据构造、主实验、消融、敏感性、表格和图件的轻量闭环。

2026-05-14:
- 新增 MVC-MOEA/D。
- 新增 MK13 二目标中等规模实验脚本。
- 补齐 MVC-EDA-TS 的 PMA/PMS/PMM、N1/N2/N3 初版 TS。

2026-05-28:
- 按两目标论文执行方案更新本清单。
- 正式成本口径改为 PC + TC + CFC。
- 新增 MK13 2VC-2Type-4SRU 固定成本数据集。
- 将价值链先验、六类邻域、自适应邻域选择列为下一阶段核心实现任务。
- 实现价值链感知 PMA 先验、六类跨链协同邻域、自适应邻域概率更新和新消融配置。
- 增加固定成本口径测试；全量测试 29 passed。
- 使用新 MK13 固定成本数据完成 MVC-EDA-TS smoke，history 已输出邻域概率日志。
```
