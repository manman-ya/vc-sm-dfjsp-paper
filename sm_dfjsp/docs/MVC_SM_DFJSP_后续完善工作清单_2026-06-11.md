# MVC-SM-DFJSP 论文后续完善工作清单

创建日期：2026-06-11  
适用项目：`D:\code\recode\vc-sm_dfjsp\sm_dfjsp`  
适用论文：面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度方法  
当前主线：MVC-SM-DFJSP, MVC-EDA-TS, 双目标 `total_cost` 与 `makespan`

## 0. 当前状态概述

当前项目已经具备一篇论文初稿所需的基本材料：

1. 已定义 MVC-SM-DFJSP 问题，核心结构为：

```text
job -> value chain ownership
    -> service type matching
    -> intra-chain/cross-chain SRU selection
    -> machine selection
    -> operation sequencing
```

2. 已统一正式双目标口径：

```text
min F1 = total_cost = processing_cost + transport_cost + cross_fixed_cost
min F2 = makespan
```

3. 已完成历史主实验：

```text
instances: MVC-MK01 ~ MVC-MK15
algorithms: NSGA-II, MOEA/D, MVC-EDA-TS
cross modes: off, on
seeds: 20260428, 20260429, 20260430, 20260431, 20260432
popsize: 80
max_iter: 150
objective_dim: 2
```

说明：上述实验已经包含 NSGA-II 和 MOEA/D 的 cross-on 结果，但根据最新论文叙事，后续定稿不建议把 NSGA-II-on 和 MOEA/D-on 作为主要对比对象。原因是通用 NSGA-II 和 MOEA/D 不包含价值链感知初始化、价值链先验概率和跨链专用邻域。强行比较它们的 cross-on 结果，容易把“算法性能比较”和“跨链协同机制验证”混在一起。

修订后的正式实验主线建议改为：

```text
Experiment 1: Algorithm comparison under intra-chain scheduling
  NSGA-II-off
  MOEA/D-off
  Plain EDA-TS-off
  MVC-EDA-TS-off

Experiment 2: Cross-chain collaboration mechanism
  MVC-EDA-TS-off
  MVC-EDA-TS-on

Experiment 3: Ablation study of MVC-EDA-TS
  Full MVC-EDA-TS
  No-VC-init
  No-prior
  No-cross-neighbors
  No-adaptive-neighborhood
  No-archive

Experiment 4: Sensitivity analysis
  fixed cross-chain cost
  transport cost scale
  cross-chain time advantage
  value-chain/SRU/service-type structure
```

新的实验叙事应明确区分两个问题：

1. 算法性能问题：在相同 cross-off 可行域下，MVC-EDA-TS 是否优于通用多目标算法和 Plain EDA-TS？
2. 协同机制问题：在 MVC-EDA-TS 框架内，允许跨链是否会改变 Pareto 前沿、成本结构和资源流动？

4. 已完成轻量消融实验：

```text
instances: mk05, mk10, mk15
variants: full, no_vc_init, no_prior, no_cross_neighbors,
          no_adaptive_neighborhood, no_archive
seeds: 20260428, 20260429, 20260430
```

5. 已完成 mk05 轻量敏感性实验，覆盖 fixed cost、transport scale 和 cross time scale。

6. 已生成 Nature 风格中文论文初稿：

```text
docs/MVC_SM_DFJSP_Nature风格论文初稿_2026-06-11.md
```

但是，从审稿视角看，当前实验仍不能直接作为高质量定稿。本次已补齐 Plain EDA-TS-off 基线和统计显著性检验；仍未完成同预算公平对比、小规模精确验证、LA 基准 LB/UB 验证、扩展消融、跨链机制强化实例、系统敏感性分析、图表和引用定稿。

### 0.1 当前执行状态总览

本次仅执行 2.4 和 2.7，其他部分保持未执行或沿用历史轻量结果。

| 章节 | 工作项 | 当前状态 | 说明 |
| --- | --- | --- | --- |
| 2.1 | 小规模精确验证 | 已完成 | 已运行 `scripts/run_mvc_small_exact_validation.py`，生成 3 个小规模实例及 `reports/mvc_small_validation/` 验证结果；6 个 instance/mode 组合均达到 exact coverage=1.0、false_nd_count=0、infeasible_count=0、exact_hv_gap=0、exact_igd=0。 |
| 2.2 | 成本与解码审计 | 未完成 | 本次未执行；仍需手工指定解的成本与调度区间审计。 |
| 2.3 | LA 基准 LB/UB 可行性验证 | 未完成 | 本次未执行；仍需构建 LA 单目标 makespan 对齐实验。 |
| 2.4 | 统计显著性检验 | 已完成 | 已合并主实验与 Plain EDA-TS-off，统一重算 metrics 并输出 Wilcoxon/Friedman 检验。 |
| 2.5 | 同预算公平对比 | 未完成 | 本次未执行；仍需 same-time 或 same-evaluation budget。 |
| 2.6 | 扩展消融实验 | 实现已完成，待运行 | 已新增 2.6 专用入口和分析汇总脚本；按用户要求本次未直接运行，仍需运行后确认扩展消融结果。 |
| 2.7 | Plain EDA-TS 基线补齐 | 已完成 | 已完成 MVC-MK01~MK15、5 seeds、cross-off、80 pop、150 iter 正式运行。 |
| 3.1 | 跨链机制强化实例 | 实例生成已完成，实验待运行 | 已为 mk14、mk15 生成链内拥堵和跨链时间优势两类机制实例；尚需运行 cross-off vs cross-on 对比并输出机制分析表图。 |
| 3.2 | 系统敏感性分析 | 未完成 | 仅有历史 mk05 轻量敏感性；本次未扩展。 |
| 3.3 | 可选补充基线与命名规范 | 未完成 | 本次未新增额外基线。 |
| 3.4 | 代表性案例分析 | 未完成 | 本次未生成案例图。 |
| 4.1-4.4 | 投稿前整理工作 | 未完成 | 本次未重建最终表图、核对引用或重写英文稿。 |

## 1. 总体完善目标

后续完善应围绕 5 个目标展开。

### 1.1 证明模型是正确的

需要证明：

1. 服务类型匹配约束正确；
2. cross-off 模式下不会发生跨链；
3. cross-on 模式下只允许同服务类型跨链；
4. 加工成本、运输成本、跨链固定协调成本计算正确；
5. makespan 计算正确；
6. 机器无重叠；
7. 工序 precedence 正确；
8. 解码结果与数学模型一致。

对应工作：小规模验证、手工解码审计、单元测试和附录说明。

### 1.2 证明算法比较是公平的

需要证明：

1. MVC-EDA-TS 的优势不是单纯来自更长运行时间；
2. NSGA-II、MOEA/D、Plain EDA-TS 和 MVC-EDA-TS 在相同 cross-off 可行域下使用相同或可解释的计算预算；
3. 结果在多个随机种子下稳定；
4. 统计检验支持论文中的性能结论。

对应工作：同时间预算实验、同评价次数实验、统计显著性检验、收敛曲线。

### 1.3 证明 MVC 机制是有贡献的

需要证明：

1. 价值链感知初始化有效；
2. 价值链先验概率模型有效；
3. 跨链协同邻域有效；
4. 非支配档案有效；
5. 自适应邻域选择至少在特定实例上有可解释贡献；
6. 在 MVC-EDA-TS 框架内，cross-on 相比 cross-off 能在合适条件下改变 Pareto 前沿、成本结构和资源流动。

对应工作：扩展消融实验、跨链机制强化实例、代表性案例分析。

### 1.4 证明结论有边界

需要证明：

1. 跨链不是无条件优于链内；
2. 跨链收益依赖固定成本、运输成本、跨链时间优势和链内负载；
3. 当前 equal-processing 数据集中跨链收益有限是合理现象；
4. 在跨链时间优势或链内拥堵增强时，跨链协同价值会更明显。

对应工作：系统敏感性分析、机制实例、讨论和限制小节。

### 1.5 证明论文可复现

需要证明：

1. 数据构造规则清楚；
2. 实验参数清楚；
3. 每张表和图都能从项目输出重建；
4. 结果文件路径和脚本入口清楚；
5. 参考文献准确。

对应工作：表图生成脚本、结果目录说明、参考文献核对、复现说明。

## 2. P0 必须完成工作

P0 是投稿前必须补齐的内容。缺少这些，审稿人很容易质疑论文可靠性。

## 2.1 小规模精确验证

执行状态：已完成。  
实现日期：2026-06-12。  
验证运行日期：2026-06-15。  
执行范围：已完成 3 个小规模实例的 exact enumeration、MVC-EDA-TS 小预算对比、成本审计和调度区间审计。

本次验证结果：
```text
instances: mvc_small_01, mvc_small_02, mvc_small_03
cross modes: off, on
algorithm seeds: 20260428, 20260429, 20260430
popsize: 40
max_iter: 80
local_search_steps: 6
```

汇总结论：
```text
all instance/mode combinations: 6
exact_coverage: 1.0 for all combinations
false_nd_count: 0 for all combinations
infeasible_count: 0 for all combinations
exact_hv_gap: 0 for all combinations
exact_igd: 0 for all combinations
```

本次新增脚本：

```text
scripts/run_mvc_small_exact_validation.py
```

脚本功能：

1. 自动生成 3 个极小 MVC-SM-DFJSP 实例；
2. 对 cross-off 和 cross-on 分别枚举 UA、OS 和 MS；
3. 调用项目现有 `evaluate_mvc_individual()` 计算 `total_cost` 和 `makespan`；
4. 提取 exact nondominated front；
5. 可选运行小预算 MVC-EDA-TS，与 exact front 比较；
6. 输出 exact coverage、false_nd_count、infeasible_count、exact_hv_gap 和 exact_igd；
7. 输出成本审计表和调度区间审计表。

脚本默认输出：

```text
data/mvc_small_validation/
reports/mvc_small_validation/
```

预期生成文件：

```text
data/mvc_small_validation/mvc_small_01.json
data/mvc_small_validation/mvc_small_02.json
data/mvc_small_validation/mvc_small_03.json
reports/mvc_small_validation/exact_front.csv
reports/mvc_small_validation/algorithm_front.csv
reports/mvc_small_validation/validation_summary.csv
reports/mvc_small_validation/validation_summary.md
reports/mvc_small_validation/cost_audit.csv
reports/mvc_small_validation/schedule_audit.csv
reports/mvc_small_validation/run_meta.json
```

推荐运行命令：

```text
python scripts/run_mvc_small_exact_validation.py
```

若只想先检查 exact enumeration 和审计表，不运行 MVC-EDA-TS，可使用：

```text
python scripts/run_mvc_small_exact_validation.py --skip-algorithm
```

### 2.1.1 为什么必须做

当前主实验主要证明启发式算法在构造实例上表现较好，但不能直接证明模型和解码器完全正确。审稿人可能会问：

1. 你的 Pareto 前沿是否只是启发式算法内部自洽？
2. total_cost 是否与数学模型一致？
3. cross-off 是否真的禁止跨链？
4. cross-on 是否正确加入跨链固定成本？
5. 解码器是否可能产生机器重叠或工序顺序错误？

小规模验证用于回答这些问题。

### 2.1.2 推荐验证方式

优先使用穷举验证，而不是依赖 Gurobi。

推荐构造 2 到 3 个极小实例：

```text
small_01:
  jobs: 3
  value chains: 2
  service types: 2
  SRUs: 4
  machines per SRU: 1
  operations per job: 1-2

small_02:
  jobs: 4
  value chains: 2
  service types: 2
  SRUs: 4
  machines per SRU: 1-2
  operations per job: 2

small_03:
  jobs: 5
  value chains: 2
  service types: 2
  SRUs: 4
  machines per SRU: 2
  operations per job: 2-3
```

对这些实例穷举：

1. 每个 job 的可行 SRU 分配；
2. 每个 operation 的可行机器选择；
3. 小规模下可枚举或受限枚举的工序排序；
4. 计算所有可行解的 total_cost 和 makespan；
5. 提取 exact nondominated front；
6. 与 MVC-EDA-TS 的输出前沿比较。

### 2.1.3 输出指标

需要输出：

| 指标 | 含义 |
| --- | --- |
| exact_front_size | 穷举得到的真实非支配解数量 |
| algorithm_front_size | MVC-EDA-TS 得到的非支配解数量 |
| exact_coverage | MVC-EDA-TS 找到真实前沿点的比例 |
| false_nd_count | 算法输出中不属于真实非支配前沿的点数量 |
| infeasible_count | 解码后违反约束的解数量 |
| exact_hv_gap | 相对真实前沿的 HV 差距 |
| exact_igd | 算法前沿到真实前沿的 IGD |

推荐验收标准：

```text
infeasible_count = 0
false_nd_count = 0 或能解释为目标值重复/近似
exact_coverage >= 90% 对 small_01 和 small_02
exact_igd 接近 0
```

### 2.1.4 论文写法

建议在实验设计中加入一节：

```text
5.X Small-scale validation of the model and decoder
```

中文可写：

> 为验证数学模型、目标函数和解码过程的一致性，本文构造 3 个可穷举的小规模 MVC-SM-DFJSP 实例。对每个实例枚举所有满足服务类型匹配、跨链模式、工序顺序和机器不重叠约束的调度方案，并提取真实 Pareto 前沿。结果表明，MVC-EDA-TS 在小规模实例上能够恢复真实非支配前沿，且未产生不可行解，验证了本文解码器、成本计算和跨链约束处理的正确性。

### 2.1.5 建议新增文件

```text
data/mvc_small_validation/
scripts/run_mvc_small_exact_validation.py
reports/mvc_small_validation/
docs/MVC_SM_DFJSP_小规模验证说明_2026-06-15.md
```

## 2.2 成本与解码审计

### 2.2.1 为什么必须做

total_cost 是本文核心目标。当前项目已经统一为：

```text
total_cost = processing_cost + transport_cost + cross_fixed_cost
```

但是论文定稿前必须给出可审计证据，证明每一项成本都按规则计算。

### 2.2.2 审计内容

选取一个小实例和一个手工指定调度解，逐项输出：

1. job -> SRU 分配；
2. 每个 job 是否跨链；
3. 每个 job 的 transport_cost；
4. 每个 job 的 cross_fixed_cost；
5. 每道 operation 的 processing_time；
6. 每道 operation 的 unit_processing_cost；
7. processing_cost 明细；
8. total_cost 汇总；
9. 每台机器的加工区间；
10. makespan 计算过程。

### 2.2.3 验收标准

```text
sum(operation processing cost) = processing_cost
sum(job transport cost) = transport_cost
sum(cross-chain fixed cost) = cross_fixed_cost
processing_cost + transport_cost + cross_fixed_cost = total_cost
max(job completion + transport_time) = makespan
```

### 2.2.4 论文写法

该部分可以放附录，不必占正文篇幅。

建议表述：

> Appendix X gives a complete cost and decoding audit for a small instance. The audit confirms that the reported total cost equals the sum of processing, transport and cross-chain fixed coordination costs, and that all machine and precedence constraints are satisfied.

## 2.3 LA 基准 LB/UB 可行性验证

### 2.3.1 为什么建议加入

项目中已经包含原始 LA 实例和 MVC-LA 扩展实例：

```text
data/la/la01.json ~ la20.json
data/mvc_la/la01_mvc_2vc_2type_4sru_equalproc_vcpenalty.json ~ la20_mvc_2vc_2type_4sru_equalproc_vcpenalty.json
```

Xie et al. 的 HGTSA 论文在 DFJSP 设定下给出了 LA01-LA20 在 2、3、4 个工厂场景中的 `UB(LB)`，目标是单目标 makespan。该结果可以作为标准 DFJSP 派生基准，用来验证本文算法在经典 LA 数据上的搜索可行性和结果量级。

但必须明确：LA 文献中的 LB/UB 不能直接证明 MVC-SM-DFJSP 双目标模型有效。当前 MVC 实例增加了 value chain、service type、SRU、transport time、transport cost 和 cross-chain fixed cost，且目标为 `total_cost` 与 `makespan`。因此，LA LB/UB 验证应作为补充的 benchmark sanity check，而不是替代小规模 exact validation 或 MVC 主实验。

### 2.3.2 推荐验证口径

优先做严格对齐的单目标验证：

```text
instances: data/la/la01.json ~ la20.json
objective: min makespan
factory settings: 2 factories, 3 factories, 4 factories
reference: HGTSA paper Table 5, Table 6, Table 7 UB(LB)
```

需要保证：

1. 使用与文献一致的 LA 实例定义；
2. 只比较 makespan，不比较 total_cost、HV 或 IGD；
3. 若文献 makespan 不含运输时间，则验证实验也不应加入 transport time；
4. 若使用 `data/mvc_la`，只能标注为 LA-derived MVC 实例，不得与文献 LB/UB 做同口径硬比较；
5. 对 MVC-LA 的 makespan 可把文献 LB 作为松弛下界参考，但不能把 gap 写成标准最优性 gap。

### 2.3.3 建议运行方案

最低方案：

```text
instances: la01-la20
factory settings: 2 factories
algorithm: Plain EDA-TS, MVC-EDA-TS without MVC-specific cost terms
seeds: 5
objective: makespan
```

理想方案：

```text
instances: la01-la20
factory settings: 2, 3, 4 factories
algorithms: Plain EDA-TS, MVC-EDA-TS-compatible variant
seeds: 10
objective: makespan
```

如果当前算法不方便切换到单目标 DFJSP 模式，则建议新增一个兼容运行入口，而不是直接复用 MVC 双目标结果：

```text
scripts/run_la_lbub_validation.py
```

该脚本只负责 LA 基准验证，不混入正式 MVC 多目标实验。

### 2.3.4 输出指标

每个实例至少输出：

| 指标 | 含义 |
| --- | --- |
| LB_ref | 文献下界 |
| UB_ref | 文献上界 |
| best_makespan | 本文算法多次运行得到的最好 makespan |
| mean_makespan | 多 seed 平均 makespan |
| std_makespan | 多 seed 标准差 |
| gap_to_LB | `(best_makespan - LB_ref) / LB_ref * 100%` |
| gap_to_UB | `(best_makespan - UB_ref) / UB_ref * 100%` |
| hit_LB | 是否达到文献 LB |
| beat_or_match_UB | 是否达到或优于文献 UB |
| runtime_s | 平均运行时间 |

推荐验收标准：

```text
LA01-LA05 and LA16-LA20: best_makespan should match known LB/UB in most cases
LA06-LA15: gap_to_LB should be small and gap_to_UB should be close to or below 0
no infeasible schedule
results reproducible over multiple seeds
```

### 2.3.5 论文写法

建议在实验部分增加一小节：

```text
5.X Benchmark sanity check on LA-derived DFJSP instances
```

中文可写：

> 为检验所提算法在经典 DFJSP 基准上的搜索可行性，本文进一步在 LA01-LA20 实例上进行 makespan 单目标验证，并参考已有 HGTSA 文献报告的 LB/UB 计算最优性差距。该实验仅用于验证算法在标准 LA 派生基准上的结果量级和稳定性；MVC-SM-DFJSP 模型本身的正确性仍由小规模精确验证、成本审计和 MVC 多目标主实验支撑。

### 2.3.6 建议新增文件

```text
data/reference_bounds/la_hgtsa_lbub.csv
scripts/run_la_lbub_validation.py
reports/la_lbub_validation/
```

`la_hgtsa_lbub.csv` 建议字段：

```text
instance,factories,LB_ref,UB_ref,source_table,source_paper
```

`reports/la_lbub_validation/` 建议输出：

```text
la_lbub_results.csv
la_lbub_summary.csv
la_lbub_gap_table.md
```

## 2.4 统计显著性检验

执行状态：已完成。  
完成日期：2026-06-11。  
执行范围：只执行本节要求的统计检验；未执行 2.5 同预算公平对比、2.6 扩展消融和 P1/P2 任务。

本次新增脚本：

```text
scripts/build_mvc_stat_tests.py
```

该脚本先合并历史主实验和 Plain EDA-TS-off 的 Pareto 点，再在统一参考前沿下重新计算 HV、IGD、GD、spacing、min_total_cost 和 min_makespan，避免直接比较不同实验目录中参考前沿不一致的 HV/IGD。

实际输出目录：

```text
reports/mvc_mk01_15_formal_80pop_150iter/main_experiment_with_plain_edats/
reports/mvc_mk01_15_formal_80pop_150iter/stat_tests/
```

已生成文件：

```text
main_experiment_with_plain_edats/pareto/all_pareto_points.csv
main_experiment_with_plain_edats/metrics/metrics_summary.csv
stat_tests/metrics_by_instance_algorithm_mode.csv
stat_tests/algorithm_off_comparison_metrics.csv
stat_tests/mechanism_mvc_metrics.csv
stat_tests/wilcoxon_hv_igd.csv
stat_tests/wilcoxon_cost_makespan.csv
stat_tests/friedman_ranking.csv
stat_tests/stat_tests_summary.md
```

本次统计口径：

```text
algorithm_off:
  NSGA-II-off
  MOEA/D-off
  Plain EDA-TS-off
  MVC-EDA-TS-off

mechanism_mvc:
  MVC-EDA-TS-off
  MVC-EDA-TS-on
```

主要结果摘要：

1. 在 cross-off 算法性能组中，MVC-EDA-TS-off 在 HV、IGD、min_total_cost 和 min_makespan 上均显著优于 NSGA-II-off、MOEA/D-off 和 Plain EDA-TS-off。
2. Plain EDA-TS-off 在 IGD 和 min_total_cost 上显著优于 NSGA-II-off 和 MOEA/D-off，但在 min_makespan 上弱于 NSGA-II-off 和 MOEA/D-off。
3. Friedman 排名显示 MVC-EDA-TS-off 在四个核心指标上平均排名最好。
4. MVC-EDA-TS-on 相比 MVC-EDA-TS-off 的 HV 和 min_makespan 改善不显著；IGD 统计上显示 off 略优。这支持“当前 equal-processing 数据下跨链收益有限，需要机制强化实例进一步展示”的论文边界叙事。

### 2.4.1 当前问题

当前主实验有均值比较，但缺少显著性检验。审稿人会认为“平均更好”不足以证明算法稳定优于基线。根据修订后的实验口径，统计检验应分成两类：算法性能检验和跨链机制检验。

### 2.4.2 需要检验的指标

至少检验：

```text
HV
IGD
min_total_cost
min_makespan
```

可选检验：

```text
GD
front_size
runtime_s
selected compromise total_cost
selected compromise makespan
```

### 2.4.3 推荐检验方法

对于两两比较：

```text
Wilcoxon signed-rank test
```

算法性能比较对象只使用 cross-off：

```text
MVC-EDA-TS-off vs NSGA-II-off
MVC-EDA-TS-off vs MOEA/D-off
MVC-EDA-TS-off vs Plain EDA-TS-off
Plain EDA-TS-off vs NSGA-II-off
Plain EDA-TS-off vs MOEA/D-off
```

跨链机制比较对象只使用本文算法：

```text
MVC-EDA-TS-on vs MVC-EDA-TS-off
```

对于多算法整体排名：

```text
Friedman test
post-hoc Holm or Nemenyi correction
```

Friedman test 建议只用于 cross-off 算法性能组：

```text
NSGA-II-off
MOEA/D-off
Plain EDA-TS-off
MVC-EDA-TS-off
```

不要把 NSGA-II-on 和 MOEA/D-on 纳入正式排名表。它们可以作为已有历史结果保留在内部记录或附录备查，但不作为定稿主线。

### 2.4.4 数据组织方式

建议以 instance 为配对单位，先对每个 instance 聚合 5 个 seed 的均值，再做检验。

示例：

```text
row = instance
columns = algorithm_mode
value = mean metric over seeds
```

不要直接把 75 个 instance-seed 运行都当作完全独立样本，因为同一 instance 下不同 seed 不是严格独立问题样本。

### 2.4.5 输出表格

建议输出：

```text
table_statistical_tests_hv_igd.csv
table_statistical_tests_cost_makespan.csv
table_algorithm_ranking.csv
```

表格列：

| metric | comparison | mean_A | mean_B | p_value | adjusted_p | better | significant |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |

### 2.4.6 论文写法

正文中不要写得太夸张。算法性能部分建议：

> Wilcoxon signed-rank tests over the 15 instances confirm whether MVC-EDA-TS-off achieves better HV and IGD than NSGA-II-off, MOEA/D-off and Plain EDA-TS-off under the same intra-chain scheduling setting. The detailed p-values are reported in Table X.

如果某些指标不显著，需要如实写：

> The improvement in min makespan is instance-dependent and is not significant for all comparisons, which is consistent with the conditional nature of cross-chain collaboration.

跨链机制部分建议：

> The cross-chain mode is evaluated within the proposed MVC-EDA-TS framework. This comparison isolates the effect of allowing cross-chain SRU selection from the effect of changing the optimizer.

## 2.5 同预算公平对比

### 2.5.1 当前问题

当前主实验中 MVC-EDA-TS 的运行时间明显高于 NSGA-II 和 MOEA/D：

```text
MVC-EDA-TS-off average runtime: 310.6 s
NSGA-II-off average runtime: 90.7 s
MOEA/D-off average runtime: 67.3 s
```

审稿人会问：MVC-EDA-TS-off 的优势是不是因为运行时间更长？修订后，同预算公平对比只需要在算法性能组中进行，即 NSGA-II-off、MOEA/D-off、Plain EDA-TS-off 和 MVC-EDA-TS-off。跨链机制组 `MVC-EDA-TS-off vs MVC-EDA-TS-on` 可以单独报告运行时间差异，但不需要把 NSGA-II-on 和 MOEA/D-on 纳入同预算主线。

### 2.5.2 推荐补充实验

至少做一类同预算实验。

优先方案：

```text
same-time budget:
  100 s
  300 s
  600 s
```

每个算法在同一 cross-off 可行域和同一时间上限下运行，记录 HV、IGD、front size、min cost、min makespan。

推荐算法组：

```text
NSGA-II-off
MOEA/D-off
Plain EDA-TS-off
MVC-EDA-TS-off
```

可选方案：

```text
same-evaluation budget:
  same number of objective evaluations
```

如果代码当前不方便统一评价次数，则先做同时间预算。

### 2.5.3 推荐实例

如果算力有限，先选代表性实例：

```text
mk01: small
mk05: small-medium
mk10: medium
mk13: medium-large
mk15: large
```

如果算力允许，扩展到 MVC-MK01 至 MVC-MK15。

### 2.5.4 输出图表

需要输出：

1. HV vs runtime 曲线；
2. IGD vs runtime 曲线；
3. final HV/IGD 同时间预算表；
4. runtime-normalized improvement 表。

### 2.5.5 论文写法

建议：

> Because MVC-EDA-TS uses local search and archive maintenance, it requires more computational time than the evolutionary baselines. To separate solution quality from computational budget, we additionally compare NSGA-II-off, MOEA/D-off, Plain EDA-TS-off and MVC-EDA-TS-off under identical wall-clock time limits. This comparison evaluates the optimizer under the same intra-chain feasible region.

如果同预算下优势不明显，也要如实写：

> Under very tight time budgets, MVC-EDA-TS is less competitive because the local search component cannot fully exploit the learned distribution. This indicates a trade-off between solution quality and computational overhead.

## 2.6 扩展消融实验

执行状态：实现已完成，实验结果待运行生成。  
实现日期：2026-06-12。  
执行范围：本次只实现扩展消融入口和结果汇总逻辑，不直接运行消融实验。

本次新增脚本：

```text
scripts/run_mvc_expanded_ablation.py
scripts/build_mvc_ablation_summary.py
```

同时增强已有脚本：

```text
scripts/run_mvc_full_ablation.py
```

实现后的默认口径对应本节最低要求：

```text
instances: mk01, mk05, mk10, mk13, mk15
seeds: 20260428, 20260429, 20260430, 20260431, 20260432
variants: A0_full, A1_no_vc_init, A2_no_prior,
          A3_no_cross_neighbors, A4_no_adaptive_neighborhood, A5_no_archive
cross_chain: on
popsize: 80
max_iter: 150
time_limit: 12000
objective_dim: 2
```

推荐运行命令：

```text
python scripts/run_mvc_expanded_ablation.py
```

若要运行理想要求，即 MVC-MK01 到 MVC-MK15 全实例：

```text
python scripts/run_mvc_expanded_ablation.py --all-instances
```

预期输出目录：

```text
reports/mvc_mk01_15_formal_80pop_150iter/ablation_expanded/
```

预期核心输出：

```text
all_instance_ablation_runs.csv
all_instance_ablation_summary.csv
all_instance_ablation_selected.csv
all_instance_ablation_history.csv
analysis/ablation_variant_summary.csv
analysis/ablation_instance_variant_metrics.csv
analysis/ablation_effect_vs_full.csv
analysis/ablation_module_indicators.csv
analysis/ablation_neighborhood_summary.csv
analysis/ablation_summary_report.md
run_meta.json
```

### 2.6.1 当前问题

当前消融只覆盖：

```text
mk05, mk10, mk15
3 seeds
```

属于轻量证据，不足以支撑强结论。

### 2.6.2 推荐扩展方案

最低要求：

```text
instances: mk01, mk05, mk10, mk13, mk15
seeds: 20260428-20260432
variants:
  full
  no_vc_init
  no_prior
  no_cross_neighbors
  no_adaptive_neighborhood
  no_archive
```

理想要求：

```text
instances: MVC-MK01 ~ MVC-MK15
seeds: 5
variants: same as above
```

### 2.6.3 重点分析问题

消融不是只看 HV，还要解释每个模块的作用。

| 模块 | 主要观察指标 |
| --- | --- |
| value-chain initialization | min_makespan, early HV, convergence speed |
| value-chain prior | HV, IGD, cross_chain_ratio |
| cross-chain neighbors | min_makespan, cross_chain_flow, cross_chain_ratio |
| adaptive neighborhood | convergence curve, accepted moves, neighborhood contribution |
| archive | front_size, spacing, HV |

### 2.6.4 当前已有初步结论

当前轻量消融中：

1. 去除价值链初始化后，平均最短 makespan 从 164.1 增至 186.2；
2. 去除非支配档案后，平均 front size 从 11.33 降至 6.22；
3. No-prior、No-cross-neighbors、No-adaptive-neighborhood 的影响不稳定。

后续实验需要确认这些趋势是否在更多实例上成立。

### 2.6.5 论文写法

建议避免过度声称每个模块都显著有效。更稳妥的写法：

> The ablation study indicates that value-chain-aware initialization and the non-dominated archive are the most consistently beneficial components under the current benchmark setting. The effects of the prior model and cross-chain neighborhoods are more instance-dependent, suggesting that their contribution becomes more visible when cross-chain alternatives provide meaningful time or load advantages.

## 2.7 Plain EDA-TS 基线补齐

执行状态：已完成。  
完成日期：2026-06-11。  
执行范围：只执行 Plain EDA-TS-off；未把 Plain EDA-TS-on 纳入正式主线。

代码实现状态：

```text
src/smdfjsp/baselines/mvc_edats_baseline.py
scripts/run_mvc_experiments.py
scripts/mvc_experiment_utils.py
```

当前项目已存在 `edats-baseline` 算法入口，其定义符合 Plain EDA-TS baseline：保留相同 MVC 数据、编码、解码器、目标函数、概率模型、基础 EDA-TS 搜索和非支配档案，同时关闭价值链感知初始化、价值链先验、跨链专用邻域、瓶颈释放、关键任务跨链迁移、高成本跨链回退和自适应 MVC 邻域选择。

本次正式运行口径：

```text
instances: MVC-MK01 ~ MVC-MK15
algorithm: edats-baseline
cross mode: off
seeds: 20260428, 20260429, 20260430, 20260431, 20260432
popsize: 80
max_iter: 150
time_limit: 12000
objective_dim: 2
```

实际输出目录：

```text
reports/mvc_mk01_15_formal_80pop_150iter/plain_edats_off/
```

已生成文件：

```text
plain_edats_off/pareto/all_pareto_points.csv
plain_edats_off/metrics/metrics_summary.csv
plain_edats_off/raw/runtime_summary.csv
plain_edats_off/raw/selected_compromise.csv
plain_edats_off/run_meta.json
```

完成情况：

```text
runs completed: 75 / 75
instances: 15
seeds per instance: 5
stop_reason: max_iter for completed runs
```

### 2.7.1 为什么必须做

根据修订后的实验口径，算法性能比较应为：

```text
NSGA-II-off
MOEA/D-off
Plain EDA-TS-off
MVC-EDA-TS-off
```

其中 Plain EDA-TS 是必需基线。没有它，审稿人无法判断 MVC-EDA-TS 的提升究竟来自 EDA-TS 主框架，还是来自本文提出的价值链感知机制。

### 2.7.2 Plain EDA-TS 定义

Plain EDA-TS 应与 MVC-EDA-TS 使用相同的 MVC-SM-DFJSP 数据、编码、解码器、目标函数和非支配排序，但去除显式价值链协同增强。

保留：

```text
1. UA / OS / OP / MS 四层编码；
2. 基本服务类型可行性修复；
3. PMA / PMS / PMM 概率模型；
4. 精英学习；
5. 基础禁忌搜索或基础局部搜索；
6. 非支配排序；
7. 非支配解档案；
8. 与 MVC-EDA-TS 相同的 total_cost 和 makespan 评价。
```

去除：

```text
1. value-chain-aware initialization；
2. value-chain prior probability；
3. cross-chain-specific neighborhoods；
4. adaptive neighborhood selection based on MVC neighborhood contribution；
5. critical job cross-chain migration；
6. high-cost cross-chain return；
7. any explicit cross-chain collaboration heuristic.
```

### 2.7.3 实验使用方式

Plain EDA-TS 只参与 cross-off 算法性能比较，不作为 cross-on 机制实验的主线对象。

正文应明确：

> Plain EDA-TS is used to isolate the contribution of the proposed MVC mechanisms from the general EDA-TS search framework. It is evaluated under the same cross-off setting as NSGA-II, MOEA/D and MVC-EDA-TS.

### 2.7.4 建议新增输出

```text
reports/mvc_mk01_15_formal_80pop_150iter/plain_edats_off/
reports/mvc_mk01_15_formal_80pop_150iter/main_experiment_with_plain_edats/
```

输出表至少包括：

```text
plain_edats_off/metrics/metrics_summary.csv
stat_tests/algorithm_off_comparison_metrics.csv
stat_tests/wilcoxon_hv_igd.csv
stat_tests/wilcoxon_cost_makespan.csv
stat_tests/friedman_ranking.csv
```

## 3. P1 强烈建议完成工作

P1 不是绝对必须，但会显著提高论文说服力。

## 3.1 跨链机制强化实例

当前状态：实例生成已完成，实验结果待运行。已新增 `scripts/build_mvc_mechanism_instances.py`，并在 `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty/` 下生成 mk14、mk15 的两类 3.1 机制实例：

```text
mk14_mvc_2vc_2type_4sru_intra_congested.json
mk14_mvc_2vc_2type_4sru_cross_time_advantage.json
mk15_mvc_2vc_2type_4sru_intra_congested.json
mk15_mvc_2vc_2type_4sru_cross_time_advantage.json
```

生成逻辑：`intra_congested` 保持加工时间同质，但按服务类型将约 75% 订单集中到 VC1，使 cross-off 下链内 SRU 更容易形成瓶颈；`cross_time_advantage` 保持原价值链分布，但将跨链 SRU 的加工时间缩放为原始值的 0.75，同时保留较高运输和固定协调成本。上述实例已通过现有 MVC JSON loader 与 `validate_mvc_instances.py` 校验。

### 3.1.1 当前问题

当前正式数据集为 equal-processing：

```text
Processing time is homogeneous across candidate SRUs.
```

这意味着链内和跨链 SRU 的加工时间相同。跨链主要增加运输成本、运输时间和固定协调成本。因此 cross-on 的平均提升有限是合理的，但这会削弱论文核心创新“跨链协同”的展示力度。

### 3.1.2 建议构造两类机制实例

#### 类型 A：链内拥堵实例

目标：证明当链内资源拥堵时，跨链资源可以释放瓶颈。

构造方式：

1. 保持加工时间相同；
2. 让某些价值链的同服务类型订单集中在同一 SRU；
3. 增加链内候选负载；
4. 保持跨链固定成本适中；
5. 观察 cross-on 是否降低 makespan 和 sru_load_std。

推荐命名：

```text
mvc_mk01_15_2vc4sru_intra_congested
```

#### 类型 B：跨链时间优势实例

目标：证明当跨链资源更快时，平台会用成本换工期。

构造方式：

1. 链内 SRU 使用原始加工时间；
2. 跨链 SRU 对部分 job 或 service type 设置 processing_time scale，例如 0.8；
3. 保留较高 transport cost 和 fixed cost；
4. 观察 cross_chain_ratio、min_makespan 和 cost increase。

推荐命名：

```text
mvc_mk01_15_2vc4sru_cross_time_advantage
```

### 3.1.3 需要输出的对比

每类机制实例至少输出：

1. cross-off vs cross-on 的 Pareto front；
2. min makespan 改善；
3. total cost 是否上升；
4. cross_chain_ratio；
5. cross_chain_flow；
6. sru_load_std；
7. selected compromise cost breakdown。

### 3.1.4 论文写法

建议作为“Mechanism analysis”或“Case study”。

中文可写：

> 在 equal-processing 数据集中，跨链 SRU 不具有加工时间优势，因此跨链协同主要表现为有成本的可行域扩展。为进一步验证跨链机制在链内拥堵和跨链时间优势场景下的作用，本文构造两类机制实例。结果显示，当链内资源形成瓶颈或跨链 SRU 具有明显时间优势时，cross-on 模式能够以有限成本增加换取更短 makespan 和更均衡的 SRU 负载。

## 3.2 系统敏感性分析

### 3.2.1 当前问题

当前敏感性分析只在 mk05 上完成，趋势清楚但范围较小。

### 3.2.2 推荐参数

建议敏感性分析覆盖：

```text
cross_fixed_cost:
  0, 50, 100, 200, 400

transport_cost_scale:
  0.8, 1.0, 1.2, 1.5

cross_time_scale:
  0.7, 0.8, 1.0, 1.2

value_chain_count:
  2, 3

sru_count:
  4, 6

service_type_count:
  2, 3
```

不要一次性做全因子爆炸实验。建议分组做：

1. 成本参数敏感性；
2. 时间优势敏感性；
3. 结构规模敏感性。

### 3.2.3 推荐实例

最低要求：

```text
mk05, mk10, mk15
```

理想要求：

```text
small: mk01, mk03, mk05
medium: mk08, mk10, mk12
large: mk13, mk14, mk15
```

### 3.2.4 输出图表

建议输出：

1. fixed_cost vs cross_chain_ratio；
2. fixed_cost vs HV/IGD；
3. cross_time_scale vs min_makespan；
4. cross_time_scale vs cross_chain_ratio；
5. transport_scale vs total_cost；
6. 2VC/3VC 或 4SRU/6SRU 结构对比表。

### 3.2.5 论文写法

重点解释：

1. 跨链固定成本越高，跨链比例越低；
2. 跨链时间优势越强，跨链比例越高；
3. 运输成本会抑制跨链，但影响通常弱于加工时间优势；
4. 结构更复杂时，MVC-EDA-TS 是否仍保持优势。

## 3.3 可选补充基线与命名规范

### 3.3.1 当前问题

P0 已经要求补齐 Plain EDA-TS。修订后的正式算法性能基线为：

```text
NSGA-II-off
MOEA/D-off
Plain EDA-TS-off
```

其中 NSGA-II 和 MOEA/D 是通用多目标算法，Plain EDA-TS 是问题相关启发式基线。Plain EDA-TS 的作用非常关键，因为它用于回答：

> 本文提升到底来自 EDA-TS 主框架，还是来自价值链感知 MVC 机制？

### 3.3.2 命名建议

论文表格中建议使用以下命名：

```text
NSGA-II
MOEA/D
Plain EDA-TS
MVC-EDA-TS
```

其中 Plain EDA-TS 表示无价值链协同增强的 EDA-TS，MVC-EDA-TS 表示本文完整算法。

Plain EDA-TS 保留 EDA-TS 主框架和 MVC-SM-DFJSP 的基本可行性处理，但去除价值链协同增强模块。

保留：

```text
1. UA / OS / OP / MS 四层编码；
2. 基本服务类型可行性修复；
3. PMA / PMS / PMM 概率模型；
4. 精英学习；
5. 基础禁忌搜索或基础局部搜索；
6. 非支配排序；
7. 非支配解档案；
8. 与 MVC-EDA-TS 相同的解码器和目标函数。
```

去除：

```text
1. value-chain-aware initialization；
2. value-chain prior probability；
3. cross-chain-specific neighborhoods；
4. adaptive neighborhood selection based on MVC neighborhood contribution；
5. critical job cross-chain migration；
6. high-cost cross-chain return；
7. any mechanism that explicitly uses cross-chain collaboration knowledge.
```

实验中，Plain EDA-TS 只参与 cross-off 算法性能比较：

```text
NSGA-II-off
MOEA/D-off
Plain EDA-TS-off
MVC-EDA-TS-off
```

不建议把 Plain EDA-TS 作为 cross-on 机制对比主线。跨链机制实验只比较：

```text
MVC-EDA-TS-off
MVC-EDA-TS-on
```

这样可以把“优化器性能”和“跨链机制效果”拆开，避免审稿人质疑通用基线没有跨链知识导致 cross-on 比较不公平。

在 Plain EDA-TS 完成后，如果仍需进一步增强实验，可选补充：

```text
GA-TS
VNS-based local search
random + repair baseline
```

### 3.3.3 论文写法

建议：

> To isolate the contribution of the proposed MVC mechanisms, we introduce Plain EDA-TS as a problem-related baseline. Plain EDA-TS uses the same encoding, decoder, objective functions and Pareto archive as MVC-EDA-TS, but removes value-chain-aware initialization, value-chain prior probabilities and MVC-specific cross-chain neighborhoods. The algorithm comparison is conducted under the cross-off setting, whereas the cross-chain mode is evaluated only within the proposed MVC-EDA-TS framework.

## 3.4 代表性案例分析

### 3.4.1 为什么需要

当前论文如果只报告表格，容易变成“算法跑分”。MVC-SM-DFJSP 的亮点是共享制造协同机制，因此需要可视化展示一个调度案例。

### 3.4.2 推荐实例

选择 1 到 2 个实例：

```text
mk08 or mk11:
  cross-on 对 makespan 改善明显

mk05:
  敏感性分析已有结果，适合机制解释

mk15:
  规模较大，适合展示算法鲁棒性
```

### 3.4.3 推荐图件

至少准备：

1. Algorithm comparison Pareto front under cross-off: NSGA-II-off vs MOEA/D-off vs Plain EDA-TS-off vs MVC-EDA-TS-off；
2. Mechanism comparison Pareto front: MVC-EDA-TS-off vs MVC-EDA-TS-on；
3. selected compromise cost breakdown；
4. selected compromise Gantt chart；
5. SRU load distribution bar chart；
6. value-chain cross-flow diagram。

### 3.4.4 论文写法

建议：

> The selected case shows how cross-chain collaboration changes the schedule. Compared with the cross-off solution, the cross-on compromise transfers a small number of orders to external SRUs. This increases fixed coordination and transport costs, but reduces the critical-chain completion time and produces a more balanced SRU load distribution.

## 4. P2 投稿前整理工作

P2 主要提升论文完整性、可读性和交付质量。

## 4.1 表格体系重建

### 4.1.1 必备表

正文建议保留 5 到 7 张表。

| 表 | 内容 |
| --- | --- |
| Table 1 | 符号定义 |
| Table 2 | 数据集与实例规模 |
| Table 3 | cross-off 算法性能平均结果：NSGA-II、MOEA/D、Plain EDA-TS、MVC-EDA-TS |
| Table 4 | MVC-EDA-TS cross-off vs cross-on 协同机制结果 |
| Table 5 | 统计显著性检验 |
| Table 6 | 消融实验 |
| Table 7 | 敏感性分析 |
| Table 8 | 小规模验证 |
| Table 9 | LA 基准 LB/UB 验证 |

### 4.1.2 表格规范

1. 每列标注方向，例如 HV ↑、IGD ↓；
2. 数值保留统一小数位；
3. 最优值加粗；
4. 次优值可用下划线或灰色；
5. 不要使用过多颜色；
6. 表题说明实例、种子、算法模式和统计口径。

## 4.2 图件体系重建

### 4.2.1 必备图

| 图 | 内容 |
| --- | --- |
| Fig. 1 | MVC-SM-DFJSP 层级结构图 |
| Fig. 2 | MVC-EDA-TS 算法流程图 |
| Fig. 3 | cross-off 算法性能 Pareto front 对比 |
| Fig. 4 | cross-off 算法性能 HV/IGD 箱线图或条形图 |
| Fig. 5 | MVC-EDA-TS cross-off vs cross-on 前沿变化 |
| Fig. 6 | 代表性折中解甘特图 |
| Fig. 7 | 成本拆分和跨链流 |
| Fig. 8 | 敏感性分析曲线 |

### 4.2.2 图件审稿风险

需要避免：

1. 只给指标图，没有调度结构图；
2. Pareto 图坐标没有单位；
3. 把算法性能比较和跨链机制比较混在同一张图里；
4. 甘特图无法看出 SRU 和 value chain；
5. 成本拆分没有显示 cross_fixed_cost；
6. 负载图没有解释跨链前后变化。

## 4.3 参考文献核对

### 4.3.1 当前问题

当前参考文献仍是待核对状态，不能直接投稿。

### 4.3.2 必须核对字段

每篇文献需要核对：

1. 作者；
2. 年份；
3. 题名；
4. 期刊；
5. 卷、期、页码或文章号；
6. DOI；
7. 是否与正文论断对应。

### 4.3.3 引用位置建议

| 论文部分 | 引用类型 |
| --- | --- |
| 引言第一段 | 共享制造、云制造、平台调度综述 |
| 引言第二段 | SM-DFJSP with supply-demand matching |
| 相关工作 2.1 | FJSP/DFJSP 经典与综述 |
| 相关工作 2.3 | DFJSP with transfer/transport |
| 方法算法 | EDA、TS、VNS、问题知识驱动调度 |
| 讨论未来工作 | DRL、动态调度、低碳调度 |

## 4.4 英文润色与 Nature 风格压缩

### 4.4.1 当前中文初稿的问题

当前中文初稿适合作为完整论文骨架，但如果投英文期刊，需要重写而不是逐句翻译。

### 4.4.2 英文稿建议

英文稿应采用：

```text
problem context -> missing capability -> proposed model -> algorithm -> evidence -> boundary
```

摘要控制在 200 到 250 词。

引言控制在 5 到 7 段：

1. 共享制造平台和调度需求；
2. SM-DFJSP 与供需匹配基础；
3. 多价值链协同缺口；
4. 本文问题定义；
5. 方法和贡献；
6. 实验和主要结果。

Discussion 要明确边界：

1. equal-processing 数据集下跨链收益有限；
2. 跨链时间优势和链内拥堵会增强协同价值；
3. 计算开销高；
4. 动态和多目标扩展留作未来工作。

## 5. 推荐执行顺序

建议按以下顺序推进。

### 阶段 1：可信性补强

优先级最高。

1. 小规模穷举验证；
2. 成本与解码审计；
3. LA 基准 LB/UB 可行性验证；
4. Plain EDA-TS-off 基线补齐；
5. cross-off 算法性能统计显著性检验；
6. cross-off 同时间预算对比。

完成后，论文可以回应最基本的可靠性和公平性审稿问题。

### 阶段 2：机制补强

1. 扩展消融实验；
2. 构造链内拥堵实例；
3. 构造跨链时间优势实例；
4. 扩展敏感性分析；
5. MVC-EDA-TS cross-off vs cross-on 机制对比图表。

完成后，论文可以更有力地证明“多服务价值链协同”不是形式化标签。

### 阶段 3：表达补强

1. 代表性案例分析；
2. 图表统一生成；
3. 参考文献核对；
4. 英文稿重写；
5. 附录和复现说明整理。

完成后，论文从实验报告提升为可投稿稿件。

## 6. 建议新增脚本与输出目录

### 6.1 小规模验证

```text
scripts/run_mvc_small_exact_validation.py
data/mvc_small_validation/
reports/mvc_small_validation/
```

输出：

```text
exact_front.csv
algorithm_front.csv
validation_summary.csv
validation_summary.md
cost_audit.csv
schedule_audit.csv
run_meta.json
```

### 6.2 LA 基准 LB/UB 验证

```text
data/reference_bounds/la_hgtsa_lbub.csv
scripts/run_la_lbub_validation.py
reports/la_lbub_validation/
```

输出：

```text
la_lbub_results.csv
la_lbub_summary.csv
la_lbub_gap_table.md
```

脚本默认只运行标准 LA/DFJSP makespan 单目标验证，不直接复用 MVC-LA 双目标结果。若需要报告 MVC-LA 结果，应单独标注为 LA-derived MVC extension，并在论文中说明其与文献 LB/UB 不是同一目标口径。

### 6.3 统计检验

```text
scripts/build_mvc_stat_tests.py
reports/mvc_mk01_15_formal_80pop_150iter/stat_tests/
```

输出：

```text
wilcoxon_hv_igd.csv
wilcoxon_cost_makespan.csv
friedman_ranking.csv
stat_tests_summary.md
```

统计检验脚本应支持两种模式：

```text
algorithm_off:
  NSGA-II-off
  MOEA/D-off
  Plain EDA-TS-off
  MVC-EDA-TS-off

mechanism_mvc:
  MVC-EDA-TS-off
  MVC-EDA-TS-on
```

### 6.4 同预算实验

```text
scripts/run_mvc_same_time_budget.py
reports/mvc_same_time_budget/
```

输出：

```text
same_time_metrics_summary.csv
hv_over_time.csv
igd_over_time.csv
runtime_fairness_summary.csv
```

同预算实验默认只运行 cross-off 算法性能组：

```text
NSGA-II-off
MOEA/D-off
Plain EDA-TS-off
MVC-EDA-TS-off
```

### 6.5 扩展消融实验

```text
scripts/run_mvc_expanded_ablation.py
scripts/run_mvc_full_ablation.py
scripts/build_mvc_ablation_summary.py
reports/mvc_mk01_15_formal_80pop_150iter/ablation_expanded/
```

输出：

```text
all_instance_ablation_runs.csv
all_instance_ablation_summary.csv
all_instance_ablation_selected.csv
all_instance_ablation_history.csv
analysis/ablation_variant_summary.csv
analysis/ablation_instance_variant_metrics.csv
analysis/ablation_effect_vs_full.csv
analysis/ablation_module_indicators.csv
analysis/ablation_neighborhood_summary.csv
analysis/ablation_summary_report.md
```

默认运行 2.6 最低要求：mk01、mk05、mk10、mk13、mk15，5 个 seed，official 六个变体，cross-on。若使用 `--all-instances`，则扩展到 MVC-MK01 至 MVC-MK15。

### 6.6 机制实例

```text
scripts/build_mvc_mechanism_instances.py
reports/mvc_mechanism_cases/
```

输出：

```text
intra_congested_metrics.csv
cross_time_advantage_metrics.csv
mechanism_case_summary.md
```

### 6.7 表图重建

```text
scripts/build_mvc_paper_tables.py
scripts/build_mvc_paper_figures.py
reports/mvc_paper_assets/
```

输出：

```text
tables/*.csv
tables/*.tex
figures/*.png
figures/*.svg
```

## 7. 投稿前检查清单

### 7.1 实验检查

- [x] 小规模 exact validation 完成；已生成 3 个小规模实例、exact front、algorithm front、summary、cost audit、schedule audit 和 run metadata；
- [ ] 解码和成本审计完成；
- [ ] LA 基准 LB/UB 可行性验证完成；
- [x] Plain EDA-TS-off 基线完成；
- [x] cross-off 算法性能统计显著性检验完成；
- [ ] MVC-EDA-TS cross-off vs cross-on 机制检验完成；本次仅完成 2.4 中的机制统计检验，尚未完成机制案例和图表；
- [ ] cross-off 同时间或同评价次数预算对比完成；
- [ ] 消融实验扩展完成；脚本已实现，待运行生成结果；
- [ ] 跨链机制实例完成；
- [ ] 敏感性分析扩展完成；
- [ ] 代表性案例图完成；
- [ ] 所有表图可由脚本重建。

### 7.2 论文检查

- [ ] 摘要中的所有数值都能追溯到表格；
- [ ] 引言中的 novelty 不夸大；
- [ ] 相关工作不是文献堆砌，而是服务于 gap；
- [ ] 模型中没有三目标和双目标混用；
- [ ] cross_variable_cost 不再作为正式目标项；
- [ ] Results 只报告观察结果；
- [ ] Discussion 解释机制和边界；
- [ ] 结论不引入新数据；
- [ ] 参考文献全部核对；
- [ ] 附录包含复现路径和主要证据来源。

### 7.3 审稿风险检查

- [ ] 能回答“为什么不是普通 SM-DFJSP 加标签”；
- [ ] 能回答“为什么跨链比例低但仍有研究价值”；
- [ ] 能回答“算法优势是否来自更长运行时间”；
- [ ] 能回答“提升来自 EDA-TS 主框架还是 MVC 价值链机制”；
- [ ] 能回答“每个算法模块是否真的有贡献”；
- [ ] 能回答“模型和解码器是否正确”；
- [ ] 能回答“结果是否统计显著”；
- [ ] 能回答“数据构造是否偏向本文算法”。

## 8. 最推荐的最小补强包

如果时间和算力有限，建议至少完成以下最小补强包。

```text
Must-have package:
1. 2-3 个小规模 exact validation；
2. LA01-LA20 的 LA 基准 LB/UB 可行性验证；
3. Plain EDA-TS-off 基线；
4. cross-off 算法性能 Wilcoxon/Friedman 统计检验；
5. 5 个代表性实例上的 cross-off 同时间预算对比；
6. MVC-EDA-TS-off vs MVC-EDA-TS-on 机制对比；
7. mk01/mk05/mk10/mk13/mk15 的扩展消融；
8. 1 个链内拥堵案例 + 1 个跨链时间优势案例；
9. 1 个代表性实例的 Pareto + Gantt + cost breakdown + cross-flow 图。
```

完成这个包后，论文的核心审稿风险会明显降低。

## 9. 一句话结论

当前项目已经具备论文初稿基础，但若面向正式投稿，下一步必须从“能跑出较好平均指标”推进到“模型可验证、比较公平、机制可解释、结论有统计支撑”。修订后的实验主线应将算法性能与跨链机制拆开：算法性能只在 cross-off 下比较 NSGA-II、MOEA/D、Plain EDA-TS 和 MVC-EDA-TS；跨链机制只比较 MVC-EDA-TS-off 与 MVC-EDA-TS-on。最优先补齐的是小规模验证、LA 基准 LB/UB 可行性验证、Plain EDA-TS-off 基线、cross-off 统计检验、cross-off 同预算对比和扩展消融；最能提升论文特色的是跨链机制强化实例、系统敏感性分析和代表性案例可视化。
