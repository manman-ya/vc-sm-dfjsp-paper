# MVC-SM-DFJSP 两目标中文核心论文完整执行方案

创建日期：2026-05-28  
适用项目：`vc-sm_dfjsp/sm_dfjsp`  
论文方向：基于共享制造的多服务价值链协同分布式柔性作业车间双目标调度

## 1. 论文定位

本文不再以“复现原 SM-DFJSP 论文”为主线，而是基于当前项目扩展为一个新问题：

> 面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度问题。

问题简称：

```text
MVC-SM-DFJSP
Multi-service Value Chain Collaborative Shared Manufacturing Distributed Flexible Job Shop Scheduling Problem
```

核心思想：

```text
原 SM-DFJSP:
订单 -> 服务类型匹配 -> SRU 选择 -> SRU 内机器选择 -> 工序排序

本文 MVC-SM-DFJSP:
订单 -> 价值链归属 -> 服务类型匹配 -> 链内/跨链 SRU 选择 -> SRU 内机器选择 -> 工序排序
```

本文只做双目标：

```text
min F1 = total_cost
min F2 = makespan
```

`max_sru_load`、`sru_load_std`、`cross_chain_ratio`、`value_chain_inflow/outflow` 只作为辅助分析指标，不作为优化目标。

## 2. 推荐论文题目

可选题目：

1. 面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度方法
2. 考虑跨链协同的共享制造分布式柔性作业车间双目标调度研究
3. 基于改进 EDA-TS 的多服务价值链共享制造双目标调度方法

推荐使用第 1 个，覆盖模型和算法两条主线。

## 3. 创新点设计

建议正式论文写 3 个创新点。

### 3.1 问题与模型创新

提出多服务价值链协同的共享制造分布式柔性作业车间双目标调度问题，在传统 SM-DFJSP 的“服务类型-SRU-机器”结构上引入订单价值链归属，形成“价值链-服务类型-SRU-机器”的层级调度机制。

该创新点强调：

- 价值链是订单业务归属，不等于服务类型。
- 服务类型是制造需求类别，不等于价值链。
- SRU 是可共享制造资源单元。
- 订单可在链内或跨链同类型 SRU 中选择资源。
- 跨链选择会引入运输成本和协同成本，但可能缩短完工时间。

### 3.2 算法机制创新

设计价值链感知的 MVC-EDA-TS 算法，在原 EDA-TS 概率模型和禁忌搜索框架上加入：

- 价值链感知 SRU 分配概率模型；
- 链内/跨链 SRU 替换邻域；
- 跨链回流邻域；
- 关键订单跨链迁移邻域；
- 成本敏感回流邻域；
- 基于非支配贡献的自适应多邻域选择。

### 3.3 实验与管理启示创新

基于 MK/FJSP benchmark 构造 MVC-MK 扩展实例，比较不允许跨链与允许跨链两种协同模式，分析跨链协同对成本-工期 Pareto 前沿、跨链调用比例和资源负载分布的影响。

## 4. 模型口径统一

投稿前必须先统一模型、代码、数据、文档中的成本定义。

### 4.1 推荐成本定义

正式论文与后续实验统一采用固定跨链协同成本口径：

```text
total_cost = processing_cost
           + transport_cost
           + cross_fixed_cost
```

其中：

```text
processing_cost   加工成本
transport_cost    运输成本
cross_fixed_cost  跨链固定协同成本
```

`cross_variable_cost` 和 `cross_chain_cost_rate` 只作为历史兼容字段保留，取值固定为 0，不参与目标函数和结果解释。不允许在代码、数据说明和论文中同时出现两套口径。

### 4.2 需要检查的文件

```text
src/smdfjsp/model/mvc_evaluator.py
src/smdfjsp/data/mvc_builder.py
data/mvc_mk01_15/README.md
docs/MVC_SM_DFJSP_论文初稿_2026-05-15.md
docs/MVC_SM_DFJSP_论文构造与整体实现新方案_2026-05-12.md
scripts/build_mvc_mk01_15.py
scripts/run_mvc_experiments.py
scripts/run_mvc_mk13_conflict_2obj_resumable.py
scripts/run_mvc_mk13_moead_50iter.py
```

### 4.3 双目标函数

目标 1：最小化总成本。

```text
F1 = PC + TC + CFC
```

目标 2：最小化最大完工时间。

```text
F2 = max_j (C_j + tt_{j,u})
```

其中 `C_j` 为订单 `j` 最后一道工序完成时间，`tt_{j,u}` 为订单选择 SRU `u` 后的运输时间。

## 5. 数学模型执行清单

### 5.1 集合

| 符号 | 含义 |
| --- | --- |
| `J` | 订单集合 |
| `V` | 服务价值链集合 |
| `T` | 服务类型集合 |
| `U` | SRU 集合 |
| `M_u` | SRU `u` 内部机器集合 |
| `O_j` | 订单 `j` 的工序集合 |
| `A_j` | 订单 `j` 的候选 SRU 集合 |
| `A_j^in` | 订单 `j` 的链内候选 SRU 集合 |
| `A_j^cross` | 订单 `j` 的跨链候选 SRU 集合 |

### 5.2 参数

| 参数 | 含义 |
| --- | --- |
| `vc_j` | 订单 `j` 所属价值链 |
| `type_j` | 订单 `j` 服务类型 |
| `vc_u` | SRU `u` 所属价值链 |
| `types_u` | SRU `u` 可服务类型集合 |
| `p_{j,o,u,m}` | 工序 `(j,o)` 在 SRU `u` 机器 `m` 上的加工时间 |
| `c_{j,o,u,m}` | 工序 `(j,o)` 在 SRU `u` 机器 `m` 上的加工成本系数 |
| `tt_{j,u}` | 订单 `j` 选择 SRU `u` 的运输时间 |
| `tc_{j,u}` | 订单 `j` 选择 SRU `u` 的运输成本 |
| `fc_{j,u}` | 跨链固定协同成本 |
| `cr_{j,u}` | 跨链变动成本率 |

### 5.3 决策变量

| 变量 | 含义 |
| --- | --- |
| `x_{j,u}` | 订单 `j` 是否分配给 SRU `u` |
| `y_{j,o,u,m}` | 工序 `(j,o)` 是否在 SRU `u` 机器 `m` 上加工 |
| `s_{j,o}` | 工序开始时间 |
| `e_{j,o}` | 工序完成时间 |
| `q_{j,u}` | 订单 `j` 是否跨链调用 SRU `u` |

工程实现中可继续使用 `UA/OS/OP/MS` 编码隐式表达上述变量。

### 5.4 约束

1. 每个订单只分配给一个 SRU。

```text
sum_u x_{j,u} = 1
```

2. 订单只能选择服务类型匹配的 SRU。

```text
x_{j,u} = 0, if type_j not in types_u
```

3. 不允许跨链时，只能选择本价值链 SRU。

```text
if cross_chain_allowed = 0:
    x_{j,u} = 0, if vc_j != vc_u
```

4. 工序只能在订单分配的 SRU 内加工。

```text
sum_{m in M_u} y_{j,o,u,m} = x_{j,u}
```

5. 同一订单内部工序满足工艺顺序。

```text
s_{j,o+1} >= e_{j,o}
```

6. 同一机器同一时刻只能加工一道工序。

该约束由解码过程和机器就绪时间隐式保证。

## 6. 算法改造方案

本文算法命名建议：

```text
MVC-EDA-TS
```

如果需要突出新机制，可在论文中解释为：

```text
Value-chain-aware EDA-TS for MVC-SM-DFJSP
```

### 6.1 总体流程

```text
输入 MVC-SM-DFJSP 实例、算法参数和 cross_chain_allowed 模式
初始化价值链感知种群
评价种群
初始化非支配解档案
初始化邻域选择概率

while 未达到终止条件:
    根据精英解和档案更新 PMA/PMS/PMM
    基于价值链感知 PMA 采样新个体
    执行可行性修复
    对精英解执行自适应多邻域禁忌搜索
    评价新个体和局部搜索个体
    更新非支配解档案
    根据邻域贡献更新邻域选择概率
    环境选择得到下一代种群

输出 Pareto 解集、指标、调度明细和图表
```

### 6.2 价值链感知初始化

初始化种群由多种策略混合生成。

| 策略 | 目的 |
| --- | --- |
| 随机初始化 | 保持多样性 |
| 链内优先 | 生成低跨链成本解 |
| 成本优先 | 降低总成本 |
| 时间优先 | 压缩完工时间 |
| 跨链收益优先 | 捕捉高价值跨链资源 |

推荐比例：

```text
20% random
20% intra-chain-first
20% cost-first
20% time-first
20% cross-gain-first
```

### 6.3 价值链感知 PMA 概率模型

当前 PMA 主要基于精英频率更新。建议改为：

```text
PMA = (1 - eta) * P_prior + eta * P_elite
```

其中 `P_elite` 来自精英解频率，`P_prior` 来自价值链感知评分。

SRU 选择评分：

```text
score(j,u) =
  a * norm_processing_cost(j,u)
+ b * norm_transport_cost(j,u)
+ c * norm_cross_cost(j,u)
+ d * norm_estimated_completion_time(j,u)
- e * norm_cross_time_gain(j,u)
```

概率转换：

```text
P_prior(j,u) = softmax(-score(j,u) / tau)
```

约束处理：

```text
if type_j not in types_u:
    P_prior(j,u) = 0

if cross_chain_allowed = 0 and vc_j != vc_u:
    P_prior(j,u) = 0
```

论文表述：

> 通过价值链感知先验，算法在链内低成本资源和跨链短工期资源之间形成有偏但可学习的采样机制。

### 6.4 跨链协同邻域

建议将禁忌搜索邻域显式拆成 6 类。

#### N1 链内 SRU 替换

```text
选择订单 j
在 A_j^in 中选择不同于当前 SRU 的候选 SRU
生成新解
```

目的：在不引入跨链成本的情况下优化成本或时间。

#### N2 跨链 SRU 替换

```text
选择订单 j
在 A_j^cross 中选择同服务类型 SRU
生成跨链调度解
```

目的：探索跨链资源对 makespan 的改进。

#### N3 跨链回流

```text
选择当前已跨链的订单 j
将其迁回 A_j^in 中的链内 SRU
```

目的：减少不必要的跨链成本。

#### N4 关键订单跨链迁移

```text
找到造成 makespan 的关键订单 j*
在 A_j*^cross 中搜索预计完工时间更短的 SRU
生成新解
```

目的：定向压缩最大完工时间。

#### N5 高成本跨链订单回流

```text
选择跨链成本较高的订单 j
尝试迁回链内 SRU 或低成本跨链 SRU
```

目的：改善成本目标。

#### N6 关键机器局部重排

```text
识别关键订单或关键机器上的工序
尝试机器替换、工序插入或相邻工序交换
```

目的：保留 DFJSP 内部调度优化能力，避免算法只在 SRU 分配层面变化。

### 6.5 自适应多邻域选择

为每类邻域设置选择概率：

```text
p = [p1, p2, p3, p4, p5, p6]
```

初始：

```text
p_k = 1 / 6
```

每轮记录邻域贡献：

```text
reward_k =
  w1 * accepted_count_k
+ w2 * nondominated_insert_count_k
+ w3 * objective_improvement_k
```

更新：

```text
p_k = (1 - rho) * p_k + rho * reward_k / sum(reward)
```

若所有 `reward_k = 0`，则回退为均匀概率。

论文表述：

> 根据各类邻域产生非支配解和目标改进的贡献动态调整邻域调用概率，从而提高成本压缩和工期压缩之间的搜索效率。

### 6.6 非支配解档案

档案用于保存搜索过程中的 Pareto 优质解。

基本要求：

- 按目标值去重；
- 只保留非支配解；
- 超出容量时按拥挤距离截断；
- 可参与下一代概率模型学习；
- 可作为局部搜索种子。

推荐容量：

```text
nd_pool_max = 300 或 500
```

## 7. 代码实现任务

### 7.1 成本口径修正

目标文件：

```text
src/smdfjsp/model/mvc_evaluator.py
src/smdfjsp/data/mvc_builder.py
```

任务：

- [x] 明确 `cross_variable_cost` 不参与总成本。
- [x] evaluator 中总成本按 `processing_cost + transport_cost + cross_fixed_cost` 计算。
- [x] 所有新生成数据中 `cross_chain_cost_rate = 0`，历史兼容字段 `cross_variable_cost = 0`。
- [ ] 补充单元测试验证成本拆分。

### 7.2 价值链感知 PMA

目标文件：

```text
src/smdfjsp/mvc_eda_ts/probability_model.py
```

任务：

- [ ] 新增 `build_value_chain_prior()`。
- [ ] 新增成本、时间、跨链收益评分。
- [ ] 支持参数 `prior_weight eta`。
- [ ] 在 `update()` 中融合先验概率和精英频率。
- [ ] 添加配置开关 `use_value_chain_prior`。

### 7.3 多邻域禁忌搜索

目标文件：

```text
src/smdfjsp/mvc_eda_ts/tabu_search.py
```

任务：

- [ ] 拆分链内替换邻域。
- [ ] 拆分跨链替换邻域。
- [ ] 新增跨链回流邻域。
- [ ] 新增关键订单跨链迁移邻域。
- [ ] 新增高成本跨链订单回流邻域。
- [ ] 保留机器替换和工序重排邻域。
- [ ] 每个邻域输出 `move_kind`，用于统计贡献。

### 7.4 自适应邻域选择

目标文件：

```text
src/smdfjsp/mvc_eda_ts/algorithm.py
```

任务：

- [ ] 新增邻域概率向量。
- [ ] 新增邻域贡献统计。
- [ ] 在每轮局部搜索后更新邻域概率。
- [ ] 输出每轮邻域概率和贡献日志。
- [ ] 添加配置开关 `use_adaptive_neighborhood`。

### 7.5 消融配置

目标文件：

```text
scripts/run_mvc_ablation.py
scripts/mvc_experiment_utils.py
```

任务：

- [ ] 增加 `no_prior`。
- [ ] 增加 `no_cross_neighbors`。
- [ ] 增加 `no_critical_migration`。
- [ ] 增加 `no_adaptive_neighborhood`。
- [ ] 增加 `no_archive`。

## 8. 实验设计

### 8.1 主实验

数据集：

```text
data/mvc_mk01_15/mk01_mvc_3vc_2type_6sru.json
...
data/mvc_mk01_15/mk15_mvc_3vc_2type_6sru.json
```

算法：

```text
NSGA-II
MOEA/D
EDA-TS baseline
MVC-EDA-TS
```

模式：

```text
cross-off
cross-on
```

运行次数：

```text
independent_runs = 20
```

若算力允许：

```text
independent_runs = 30
```

计算预算：

```text
population_size = 100
max_iter = 150 或 200
```

关键要求：

- 所有算法使用相同种群规模；
- 所有算法使用相同最大迭代次数或最大评价次数；
- 若 MVC-EDA-TS 局部搜索导致耗时明显更长，需要额外报告同时间预算结果。

### 8.2 协同机制实验

目的：验证允许跨链是否改善成本-工期 Pareto 前沿。

对比：

```text
NSGA-II-cross-off vs NSGA-II-cross-on
MOEA/D-cross-off vs MOEA/D-cross-on
EDA-TS-cross-off vs EDA-TS-cross-on
MVC-EDA-TS-cross-off vs MVC-EDA-TS-cross-on
```

关注：

- cross-on 是否降低最短 makespan；
- cross-on 是否扩大 Pareto 前沿；
- cross-on 是否导致成本上升；
- MVC-EDA-TS 是否能以较低跨链比例获得较大工期收益。

### 8.3 算法性能实验

指标：

| 指标 | 含义 |
| --- | --- |
| HV | 前沿收敛性和分布性，越大越好 |
| IGD | 到参考前沿距离，越小越好 |
| GD | 生成前沿到参考前沿距离，越小越好 |
| Spacing | 分布均匀性，越小越好 |
| C-metric | 两算法前沿覆盖关系 |
| Front size | 非支配解数量 |
| Runtime | 运行时间 |
| Min cost | 最低成本 |
| Min makespan | 最短完工时间 |

### 8.4 消融实验

数据：

```text
建议选择 mk05、mk10、mk13、mk15
或直接使用 MVC-MK01~15 的轻量参数版本
```

模式：

```text
cross-on
```

消融版本：

```text
Full MVC-EDA-TS
No-Prior
No-CrossN
No-Critical
No-Adaptive
No-Archive
```

指标：

```text
HV
IGD
Front size
Min makespan
Min cost
Cross-chain ratio
Runtime
```

论文中重点解释：

- 去掉价值链先验后，是否更难找到高质量跨链解；
- 去掉跨链邻域后，makespan 是否变差；
- 去掉关键订单迁移后，最短完工时间是否变差；
- 去掉自适应邻域后，HV/IGD 是否下降；
- 去掉档案后，前沿规模和稳定性是否下降。

### 8.5 敏感性分析

建议只做 3 类，保证聚焦。

#### 跨链固定成本

```text
cross_fixed_cost_factor in {0.5, 1.0, 1.5, 2.0}
```

观察：

- 跨链比例是否下降；
- 总成本是否上升；
- makespan 是否变差。

#### 运输成本系数

```text
transport_cost_factor in {0.5, 1.0, 1.5, 2.0}
```

观察：

- 运输成本是否抑制跨链；
- 跨链协同是否仍能带来工期收益。

#### 跨链资源速度优势

```text
cross_speed_advantage in {weak, medium, strong}
```

观察：

- 速度优势越强，makespan 是否下降；
- 跨链比例是否上升；
- MVC-EDA-TS 是否比基准算法更能捕捉少量高价值跨链机会。

### 8.6 统计检验

必须输出：

```text
Wilcoxon signed-rank test
Friedman average rank
```

建议比较对象：

```text
MVC-EDA-TS vs NSGA-II
MVC-EDA-TS vs MOEA/D
MVC-EDA-TS vs EDA-TS baseline
```

指标：

```text
HV
IGD
GD
```

## 9. 图表清单

### 9.1 表格

| 表号 | 内容 |
| --- | --- |
| 表 1 | 符号定义 |
| 表 2 | 算法参数设置 |
| 表 3 | MVC-MK 数据集规模 |
| 表 4 | 主实验 HV/IGD/GD/Spacing 平均结果 |
| 表 5 | cross-off 与 cross-on 协同效果对比 |
| 表 6 | 消融实验结果 |
| 表 7 | 敏感性分析结果 |
| 表 8 | Wilcoxon / Friedman 统计检验 |

### 9.2 图片

| 图号 | 内容 |
| --- | --- |
| 图 1 | MVC-SM-DFJSP 层级调度结构图 |
| 图 2 | MVC-EDA-TS 算法流程图 |
| 图 3 | 价值链感知 PMA 更新示意图 |
| 图 4 | 跨链协同邻域示意图 |
| 图 5 | 典型实例 Pareto 前沿对比 |
| 图 6 | cross-off vs cross-on Pareto 对比 |
| 图 7 | 折中解甘特图 |
| 图 8 | 成本拆分图 |
| 图 9 | 跨链比例敏感性曲线 |
| 图 10 | 邻域选择概率演化图 |

## 10. 论文结构

### 第 1 章 绪论

写作重点：

- 共享制造平台聚合分散制造资源；
- 多服务价值链下链内/跨链资源协同需求；
- 现有 SM-DFJSP 偏服务类型匹配，缺少价值链协同描述；
- 本文研究内容和创新点。

### 第 2 章 相关研究

建议分 4 节：

1. 共享制造与供需匹配；
2. 分布式柔性作业车间调度；
3. 多价值链协同与跨链资源共享；
4. 多目标进化算法与 EDA-TS。

### 第 3 章 问题描述与双目标模型

包括：

- 应用场景；
- 基本假设；
- 符号定义；
- 决策变量；
- 双目标函数；
- 约束条件；
- 问题复杂性说明。

### 第 4 章 MVC-EDA-TS 算法

包括：

- 编码与解码；
- 价值链感知初始化；
- 价值链感知 PMA；
- 跨链协同邻域；
- 自适应多邻域选择；
- 非支配解档案；
- 算法流程与复杂度分析。

### 第 5 章 实例构造与实验设计

包括：

- MK/FJSP benchmark 来源；
- MVC-MK 扩展规则；
- 价值链、服务类型和 SRU 构造；
- 成本与运输参数；
- 对比算法；
- 参数设置；
- 评价指标；
- 实验环境。

### 第 6 章 实验结果与分析

包括：

1. 算法性能对比；
2. 跨链协同机制分析；
3. 消融实验；
4. 敏感性分析；
5. 折中解和管理启示。

### 第 7 章 结论与展望

总结：

- 提出 MVC-SM-DFJSP 双目标模型；
- 设计价值链感知 MVC-EDA-TS；
- 构造 MVC-MK 数据集；
- 验证跨链协同和算法有效性。

展望：

- 动态订单；
- 机器故障；
- 工序跨 SRU 转移；
- 碳排放目标；
- 多平台协同。

## 11. 推荐执行顺序

### 阶段 A：口径统一

- [x] 确认跨链变动成本不纳入总成本。
- [x] 修改 evaluator 和新生成数据口径为固定成本。
- [ ] 更新数据集 README。
- [ ] 更新论文初稿中的目标函数。
- [ ] 补充成本拆分测试。

验收标准：

```text
代码、数据说明、论文公式中的 total_cost 完全一致。
```

### 阶段 B：算法改造

- [ ] 实现价值链感知 PMA 先验。
- [ ] 实现跨链替换、回流、关键订单迁移邻域。
- [ ] 实现自适应邻域选择。
- [ ] 输出邻域贡献日志。
- [ ] 增加消融配置。

验收标准：

```text
所有新增模块可通过配置开关独立关闭，并能形成消融实验版本。
```

### 阶段 C：小规模验证

实例：

```text
mk05
mk13
```

运行：

```text
NSGA-II
MOEA/D
EDA-TS baseline
MVC-EDA-TS
```

模式：

```text
cross-off
cross-on
```

验收标准：

```text
能输出 Pareto CSV、指标表、折中解、甘特图、成本拆分和跨链比例。
```

### 阶段 D：主实验

- [ ] 跑 MVC-MK01~15。
- [ ] 每算法每模式 20 次独立运行。
- [ ] 生成主实验指标。
- [ ] 生成统计检验。

验收标准：

```text
形成可直接放入论文的主实验表格和 Pareto 图。
```

### 阶段 E：消融实验

- [ ] Full MVC-EDA-TS。
- [ ] No-Prior。
- [ ] No-CrossN。
- [ ] No-Critical。
- [ ] No-Adaptive。
- [ ] No-Archive。

验收标准：

```text
能证明至少 2 到 3 个核心模块对 HV/IGD/makespan 有明显贡献。
```

### 阶段 F：敏感性分析

- [ ] 跨链固定成本。
- [ ] 运输成本系数。
- [ ] 跨链资源速度优势。

验收标准：

```text
得到跨链比例、成本和工期随参数变化的曲线。
```

### 阶段 G：论文成稿

- [ ] 完成模型章节。
- [ ] 完成算法章节。
- [ ] 完成实验章节。
- [ ] 统一图表格式。
- [ ] 补齐参考文献。
- [ ] 删除“阶段性结果”“待补”等草稿表述。

## 12. 风险与处理

### 风险 1：算法创新不足

处理：

- 必须实现价值链感知 PMA；
- 必须实现跨链协同专用邻域；
- 最好实现自适应邻域选择；
- 用消融实验量化贡献。

### 风险 2：cross-on 效果不明显

处理：

- 检查跨链资源是否真的有时间优势；
- 调整跨链固定成本和运输成本；
- 使用敏感性分析说明跨链协同存在适用区间。

### 风险 3：MVC-EDA-TS 耗时过长

处理：

- 报告同迭代预算和同时间预算两套结果；
- 限制局部搜索步数；
- 减少每轮局部搜索种子数量；
- 使用邻域候选筛选。

### 风险 4：负载指标被误解为目标

处理：

- 论文中明确本文为双目标；
- 负载只作为辅助诊断指标；
- 不写“优化负载均衡”，只写“分析资源负载变化”。

### 风险 5：历史实验结果口径不一致

处理：

- 正式论文只使用统一口径后重跑的结果；
- 历史结果可保留在 reports 中，但不要进入正文。

## 13. 最小可投稿闭环

如果时间有限，至少完成：

```text
1. 双目标 MVC-SM-DFJSP 模型
2. 价值链感知 MVC-EDA-TS
3. MVC-MK01~15 主实验
4. cross-off/cross-on 协同对比
5. 4 个消融版本
6. 3 类敏感性分析
7. Wilcoxon 或 Friedman 统计检验
```

最小对比算法：

```text
NSGA-II
MOEA/D
EDA-TS baseline
MVC-EDA-TS
```

最小论文结论：

> 允许跨链协同可以扩展共享制造调度的成本-工期 Pareto 搜索空间；所提 MVC-EDA-TS 通过价值链感知概率学习和跨链协同邻域，能够更稳定地获得高质量非支配解，并在部分实例中以有限跨链成本换取更短完工时间。

## 14. 当前项目与方案对应关系

| 方案内容 | 当前项目状态 | 后续动作 |
| --- | --- | --- |
| MVC 数据结构 | 已有 | 检查字段口径 |
| MVC evaluator | 已有 | 统一跨链成本计算 |
| MVC-MK01~15 数据集 | 已有 | 统一 README 和参数 |
| NSGA-II baseline | 已有 | 补 cross-off/cross-on 全实验 |
| MOEA/D baseline | 已有 | 补 cross-off/cross-on 全实验 |
| EDA-TS baseline | 已有 | 确认与 MVC-EDA-TS 差异 |
| MVC-EDA-TS | 已有初版 | 增强 PMA、邻域和自适应选择 |
| 消融脚本 | 已有基础 | 增加新消融版本 |
| 敏感性脚本 | 已有基础 | 聚焦三类正式敏感性 |
| 图表脚本 | 已有 | 增加邻域概率演化图 |
| 论文初稿 | 已有 | 改为两目标正式口径 |

## 15. 推荐下一步

下一步优先顺序：

```text
1. 统一 total_cost 口径
2. 实现价值链感知 PMA
3. 显式拆分跨链邻域
4. 实现关键订单跨链迁移
5. 实现自适应邻域选择
6. 用 mk05/mk13 做 smoke 实验
7. 再跑 MVC-MK01~15 正式实验
```

这条路线的核心判断：

> 两目标版本可以不依赖第三目标形成创新，但必须让算法真正理解“价值链-服务类型-SRU”的结构，并通过价值链感知概率模型和跨链协同邻域体现问题特定搜索能力。
