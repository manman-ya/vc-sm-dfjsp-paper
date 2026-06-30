# MVC-SM-DFJSP 双目标论文方法实现文档

创建日期：2026-06-07  
适用项目：`D:\code\recode\vc-sm_dfjsp\sm_dfjsp`  
论文方向：面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度  
推荐算法名：MVC-EDA-TS  
英文全称：Value-chain-aware Multi-objective Estimation of Distribution Algorithm with Tabu Search for MVC-SM-DFJSP

## 1. 文档目的

本文档用于统一论文、模型、算法、代码和实验口径。当前论文应以双目标为主：

```text
min F1 = total_cost
min F2 = makespan
```

`max_sru_load`、`sru_load_std`、`cross_chain_ratio`、`value_chain_inflow`、`value_chain_outflow`、`cross_chain_flow` 作为辅助诊断指标和管理启示指标，不作为正式优化目标。这样可以避免论文模型写三目标、实验只做双目标导致的审稿风险。

本文档强调一个核心判断：本论文的主要创新不应写成“在 EDA-TS 上加几个算子”，而应写成：

```text
新问题定义：多服务价值链协同的 MVC-SM-DFJSP
+ 新协同机制：链内/跨链 SRU 选择与固定协同成本
+ 新求解方法：价值链感知概率模型和跨链协同邻域的 MVC-EDA-TS
+ 新实验分析：跨链协同对成本-工期 Pareto 前沿和资源流动的影响
```

## 2. 论文定位

### 2.1 背景定位

共享制造平台连接多个订单来源、多个价值链和多个制造资源单元。传统柔性作业车间调度主要关注：

```text
job -> operation -> machine
```

分布式柔性作业车间调度进一步关注：

```text
job -> factory/SRU -> machine -> operation sequence
```

共享制造下的 SM-DFJSP 已经引入服务资源单元 SRU 和供需匹配关系，通常关注：

```text
job -> service type matching -> SRU -> machine
```

但在多服务价值链协同场景下，订单的业务归属和制造服务需求并不是同一个概念。订单属于哪条价值链，反映其客户、业务链、协同关系或平台管理边界；订单需要什么服务类型，反映其加工能力需求。两者必须分离建模。

因此本文提出 MVC-SM-DFJSP：

```text
job -> value chain ownership
    -> service type matching
    -> intra-chain/cross-chain SRU selection
    -> machine selection
    -> operation sequencing
```

### 2.2 需要突出的问题差异

论文必须明确说明 MVC-SM-DFJSP 与既有 SM-DFJSP 的差异。建议写成如下逻辑：

```text
SM-DFJSP:
  订单只需要匹配服务类型，SRU 是否可用主要由服务能力决定。

MVC-SM-DFJSP:
  订单除了匹配服务类型，还具有固定价值链归属。
  同一服务类型下，链内 SRU 与跨链 SRU 的协同成本、运输成本和调度意义不同。
  跨链 SRU 可能缩短工期或释放瓶颈，但会产生额外固定协同成本。
```

如果不强调这一点，审稿人可能认为本文只是给 SRU 增加一个标签。因此论文中必须给出一个小型示例：同一订单可选两个服务类型相同的 SRU，其中链内 SRU 成本低但排队长，跨链 SRU 加工快但固定协同成本高。此时会产生典型的成本-工期 Pareto 折中。这就是价值链层改变问题结构的证据。

## 3. 推荐创新点

### 3.1 创新点一：多服务价值链协同调度问题

提出 MVC-SM-DFJSP。该问题在共享制造平台中同时考虑：

1. 订单所属价值链；
2. 订单服务类型需求；
3. SRU 所属价值链；
4. SRU 可服务类型；
5. 链内/跨链候选 SRU；
6. 跨链固定协同成本；
7. 运输成本和运输时间；
8. SRU 内部机器选择和工序排序。

论文中建议这样概括：

> Different from existing shared manufacturing scheduling models that mainly match service type and resource capability, MVC-SM-DFJSP explicitly distinguishes the business value-chain ownership of orders from their manufacturing service requirements. This distinction enables the platform to model intra-chain and cross-chain resource collaboration under cost-time trade-offs.

### 3.2 创新点二：链内/跨链协同机制

定义每个订单 `j` 的候选 SRU：

```text
A_j = A_j^in union A_j^cross
```

其中：

```text
A_j^in    = 满足服务类型匹配且与订单属于同一价值链的 SRU
A_j^cross = 满足服务类型匹配但属于其他价值链的 SRU
```

当 `cross_chain_allowed = 0` 时：

```text
A_j = A_j^in
```

当 `cross_chain_allowed = 1` 时：

```text
A_j = A_j^in union A_j^cross
```

跨链选择会产生固定协同成本：

```text
cross_fixed_cost(j,u) > 0, if vc_j != vc_u
cross_fixed_cost(j,u) = 0, if vc_j = vc_u
```

当前项目统一采用固定跨链协同成本口径：

```text
total_cost = processing_cost + transport_cost + cross_fixed_cost
```

`cross_chain_cost_rate` 和 `cross_variable_cost` 只作为历史兼容字段，正式双目标模型中固定为 0，不参与目标函数和结果解释。

### 3.3 创新点三：价值链感知 MVC-EDA-TS

提出 MVC-EDA-TS。它不是普通 EDA-TS 的直接套用，而是在三处引入价值链知识：

1. 价值链感知初始化；
2. 价值链先验概率模型；
3. 跨链协同禁忌搜索邻域。

同时保留多目标非支配记忆池，使算法在成本和工期之间保持多样化 Pareto 前沿。

### 3.4 创新点四：协同模式实验分析

实验不只比较算法指标，还要比较：

```text
不允许跨链 vs 允许跨链
```

并分析：

```text
Pareto front shift
cross_chain_ratio
cross_chain_flow
value_chain_inflow
value_chain_outflow
SRU load distribution
cost breakdown
```

这一部分是论文从“算法跑分”变成“共享制造协同机制研究”的关键。

## 4. 问题定义

### 4.1 集合

| 符号 | 含义 | 项目对应 |
| --- | --- | --- |
| `J` | 订单集合 | `instance.jobs` |
| `V` | 价值链集合 | `job.value_chain_id`, `sru.value_chain_id` |
| `T` | 服务类型集合 | `job.service_type_id`, `sru.service_type_ids` |
| `U` | SRU 集合 | `instance.srus` |
| `M_u` | SRU `u` 内机器集合 | `sru.machines` |
| `O_j` | 订单 `j` 的工序集合 | `job.operations` |
| `A_j` | 订单 `j` 的候选 SRU 集合 | `build_mvc_compatible_sru_map` |
| `A_j^in` | 链内候选 SRU | `get_intra_chain_srus` |
| `A_j^cross` | 跨链候选 SRU | `get_cross_chain_srus` |

### 4.2 参数

| 参数 | 含义 | 项目对应 |
| --- | --- | --- |
| `vc_j` | 订单 `j` 所属价值链 | `job.value_chain_id` |
| `type_j` | 订单 `j` 服务类型 | `job.service_type_id` |
| `vc_u` | SRU `u` 所属价值链 | `sru.value_chain_id` |
| `types_u` | SRU `u` 可服务类型集合 | `sru.service_type_ids` |
| `p_{j,o,u,m}` | 工序加工时间 | `option_index[(j,o,u)][m][0]` |
| `c_{j,o,u,m}` | 单位加工成本系数 | `option_index[(j,o,u)][m][1]` |
| `tt_{j,u}` | 运输时间 | `instance.transport_time[(j,u)]` |
| `tc_{j,u}` | 运输成本 | `instance.transport_cost[(j,u)]` |
| `fc_{j,u}` | 跨链固定协同成本 | `instance.cross_chain_fixed_cost[(j,u)]` |
| `is_cross_{j,u}` | 是否跨链 | `instance.is_cross_chain[(j,u)]` |

### 4.3 决策变量

| 变量 | 含义 | 项目编码 |
| --- | --- | --- |
| `x_{j,u}` | 订单 `j` 是否分配给 SRU `u` | `UA[j] = u` |
| `y_{j,o,u,m}` | 工序是否在 SRU `u` 的机器 `m` 上加工 | `OP + MS` |
| `s_{j,o}` | 工序开始时间 | evaluation records |
| `e_{j,o}` | 工序结束时间 | evaluation records |
| `q_{j,u}` | 订单是否跨链分配 | `is_cross_chain[(j,u)]` |

工程实现不直接构造全部二元变量，而使用 `UA/OS/OP/MS` 四层编码隐式表达调度方案。

## 5. 双目标数学模型

### 5.1 目标函数

目标 1：最小化总成本。

```text
F1 = PC + TC + CFC
```

其中：

```text
PC  = processing_cost
TC  = transport_cost
CFC = cross_fixed_cost
```

加工成本：

```text
PC = sum_j sum_o sum_u sum_m p_{j,o,u,m} * c_{j,o,u,m} * y_{j,o,u,m}
```

运输成本：

```text
TC = sum_j sum_u tc_{j,u} * x_{j,u}
```

跨链固定协同成本：

```text
CFC = sum_j sum_u fc_{j,u} * q_{j,u}
```

目标 2：最小化最大完工时间。

```text
F2 = max_j (C_j + tt_{j,u})
```

其中 `C_j` 为订单 `j` 最后一道工序结束时间，`tt_{j,u}` 为订单选择 SRU `u` 后的运输时间。

### 5.2 约束条件

每个订单只分配给一个 SRU：

```text
sum_u x_{j,u} = 1, for all j
```

订单只能选择服务类型匹配的 SRU：

```text
x_{j,u} = 0, if type_j not in types_u
```

不允许跨链时，订单只能选择链内 SRU：

```text
if cross_chain_allowed = 0:
    x_{j,u} = 0, if vc_j != vc_u
```

跨链变量定义：

```text
q_{j,u} = 1, if x_{j,u} = 1 and vc_j != vc_u
q_{j,u} = 0, otherwise
```

工序只能在订单分配的 SRU 内加工：

```text
sum_m y_{j,o,u,m} = x_{j,u}
```

同一订单工序满足先后顺序：

```text
s_{j,o+1} >= e_{j,o}
```

机器同一时刻只能加工一道工序，且加工不可中断。工程实现中由解码过程维护 `machine_ready` 和 `job_ready` 保证。

## 6. 编码与解码

### 6.1 四层编码

MVC-EDA-TS 使用四层编码：

```text
UA: Unit Assignment
OS: Operation Sequence
OP: Operation list per SRU
MS: Machine Selection
```

#### UA 层

`UA[j] = u` 表示订单 `j` 分配给 SRU `u`。UA 是本文价值链创新最核心的编码层。

UA 必须满足：

```text
u in A_j
```

若 `cross_chain_allowed = 0`，则：

```text
u in A_j^in
```

若 `cross_chain_allowed = 1`，则：

```text
u in A_j^in union A_j^cross
```

#### OS 层

OS 表示同一服务类型内部的订单工序排列。项目中按服务类型维护 OS：

```text
OS[type_id] = [job_id, job_id, ...]
```

每个订单在 OS 中出现次数等于其工序数量。解码时第 `k` 次出现表示该订单的第 `k` 道工序。

#### OP 层

OP 由 UA 和 OS 推导：

```text
OP[u] = [(job_id, op_id), ...]
```

表示 SRU `u` 内部需要加工的工序队列。

#### MS 层

MS 表示每个 SRU 内部每道工序选择哪台机器：

```text
MS[u][position] = machine_id
```

### 6.2 解码过程

解码顺序：

1. 检查 OS 工序数量是否合法；
2. 检查 UA 是否满足服务类型和跨链模式约束；
3. 若 OP 为空，则由 `UA + OS` 生成 OP；
4. 按 OP 顺序遍历每个 SRU 的工序队列；
5. 对每道工序读取 MS 指定机器；
6. 计算开始时间：

```text
start = max(job_ready[j], machine_ready[u,m])
```

7. 计算结束时间：

```text
end = start + processing_time
```

8. 更新 `job_ready`、`machine_ready`、`sru_loads` 和 `processing_cost`；
9. 所有工序完成后加入运输时间、运输成本和跨链固定成本；
10. 返回双目标和辅助诊断指标。

项目对应实现：

```text
src/smdfjsp/model/mvc_evaluator.py
src/smdfjsp/model/mvc_repair.py
src/smdfjsp/core/encoding.py
```

## 7. MVC-EDA-TS 总体流程

### 7.1 算法输入

```text
MVC-SM-DFJSP instance
MVCEDATSConfig
MVCModeConfig(cross_chain_allowed, objective_dim=2)
```

核心参数：

| 参数 | 建议值 | 含义 |
| --- | --- | --- |
| `popsize` | 50-100 | 种群规模 |
| `max_iter` | 100-200 | 最大迭代次数 |
| `time_limit_s` | 600 或统一时间上限 | 单次运行时间限制 |
| `alpha` | 0.5 | UA 概率模型学习率 |
| `beta` | 0.5 | OS 概率模型学习率 |
| `gamma` | 0.5 | MS 概率模型学习率 |
| `mu` | 0.1-0.2 | 精英比例 |
| `prior_weight` | 0.25-0.40 | 价值链先验权重 |
| `local_search_steps` | 8-20 | 禁忌搜索步数 |
| `nd_pool_max` | 300-500 | 非支配档案容量 |

### 7.2 总体伪代码

```text
Input: instance, algorithm config, cross_chain_allowed
Output: non-dominated solution archive

1. Build candidate SRU sets for each job.
2. Build value-chain-aware prior probability model.
3. Initialize population by MVC-aware sampling.
4. Evaluate population.
5. Initialize non-dominated archive.

6. while stopping criterion is not met:
7.     Select elites by Pareto rank and crowding distance.
8.     Build learning set from elites and archive.
9.     Update PMA/PMS/PMM.
10.    Sample new population from probability model.
11.    Repair and evaluate new population.
12.    Select search seeds from archive or elites.
13.    Apply value-chain-aware tabu search.
14.    Update adaptive neighborhood probabilities.
15.    Update non-dominated archive.
16.    Select next population by Pareto rank and crowding distance.
17.    Record iteration metrics.

18. Return archive.
```

项目对应实现：

```text
src/smdfjsp/mvc_eda_ts/algorithm.py
```

## 8. 价值链感知初始化

### 8.1 设计动机

完全随机初始化容易产生两类问题：

1. 初始解大量落在不可解释区域，如盲目跨链导致成本过高；
2. 缺少能快速揭示成本-工期折中的代表性解。

因此初始化应让种群同时覆盖：

```text
低成本链内方案
低工期跨链方案
随机探索方案
```

### 8.2 推荐策略

论文可描述 5 类初始化策略：

| 策略 | 含义 | 作用 |
| --- | --- | --- |
| random | 随机选择可行 SRU 和机器 | 保持多样性 |
| intra-chain-first | 优先链内 SRU | 生成低协同成本解 |
| cost-first | 选择估计总成本低的 SRU/机器 | 改善 F1 |
| time-first | 选择估计完成时间短的 SRU/机器 | 改善 F2 |
| cross-gain-first | 选择跨链时间收益明显的 SRU | 探索成本换工期区域 |

建议论文写法：

```text
The initial population is generated by a mixture of random, intra-chain-first,
cost-oriented, time-oriented and cross-chain-gain-oriented strategies, so that
both conservative intra-chain schedules and aggressive cross-chain collaboration
schedules are represented at the beginning of the search.
```

当前项目中，价值链初始化由如下模块支持：

```text
src/smdfjsp/mvc_eda_ts/initialization.py
src/smdfjsp/mvc_eda_ts/algorithm.py
```

如果后续补代码，建议把 5 类策略显式记录到 `ind.aux["init_strategy"]`，以便消融实验和论文统计。

## 9. 价值链先验概率模型

### 9.1 概率模型组成

MVC-EDA-TS 使用三类概率模型：

```text
PUA/PMA: 订单到 SRU 的分配概率
PMS: 服务类型内 OS 位置概率
PMM: 工序机器选择概率
```

本文的核心改进发生在 UA 概率模型。UA 直接决定链内/跨链资源选择，因此应嵌入价值链先验。

### 9.2 先验评分函数

对每个订单 `j` 和候选 SRU `u`，构造估计评分：

```text
score(j,u) =
  w1 * norm_processing_cost(j,u)
+ w2 * norm_transport_cost(j,u)
+ w3 * norm_cross_fixed_cost(j,u)
+ w4 * norm_completion_estimate(j,u)
- w5 * norm_cross_time_gain(j,u)
```

项目当前实现采用近似权重：

```text
w1 = 0.30
w2 = 0.25
w3 = 0.25
w4 = 0.20
w5 = 0.20
```

其中：

```text
processing_cost(j,u)     = 订单所有工序在 SRU u 上的最小加工成本估计
transport_cost(j,u)      = 订单选择 SRU u 的运输成本
cross_fixed_cost(j,u)    = 订单选择 SRU u 的跨链固定协同成本
completion_estimate(j,u) = 最小加工时间估计 + 运输时间
cross_time_gain(j,u)     = max(0, best_intra_completion(j) - completion_estimate(j,u))
```

注意：`cross_time_gain` 是收益项，因此在评分中取负号。它鼓励算法在跨链能明显缩短工期时提高跨链 SRU 的采样概率。

### 9.3 先验概率

评分转概率：

```text
P_prior(j,u) = exp(-(score(j,u)-min_score_j)/tau) / sum_v exp(-(score(j,v)-min_score_j)/tau)
```

`tau` 为温度参数。温度越低，模型越偏好评分最优的 SRU；温度越高，采样越均匀。

### 9.4 精英学习与先验融合

每轮迭代中，根据精英解统计订单-SRU 分配频率：

```text
P_elite(j,u) = freq_elite(j,u)
```

再与先验融合：

```text
P_target(j,u) = (1 - lambda) * P_elite(j,u) + lambda * P_prior(j,u)
```

最后更新概率：

```text
PMA_new(j,u) = (1 - alpha) * PMA_old(j,u) + alpha * P_target(j,u)
```

其中：

```text
lambda = prior_weight
alpha  = UA probability learning rate
```

项目对应实现：

```text
src/smdfjsp/mvc_eda_ts/probability_model.py
```

### 9.5 论文贡献表述

建议在算法章节中这样写：

> Instead of learning the assignment probability solely from elite frequencies, the proposed MVC-EDA-TS incorporates a value-chain-aware prior into the UA probability model. The prior evaluates each candidate SRU by processing cost, transportation cost, cross-chain fixed collaboration cost, estimated completion time and cross-chain time gain. Therefore, the sampling process is biased but still learnable, allowing the algorithm to balance intra-chain cost advantages and cross-chain time benefits.

## 10. 非支配档案

### 10.1 作用

非支配档案用于保存搜索过程中发现的 Pareto 优质解。其作用有三点：

1. 防止优质非支配解在种群选择中丢失；
2. 为概率模型提供更稳定的学习样本；
3. 为禁忌搜索提供高质量局部搜索起点。

### 10.2 更新规则

每轮迭代后，将新种群和局部搜索解加入档案：

```text
Archive <- nondominated(Archive union NewPopulation union LocalSearchSolutions)
```

如果档案超过容量，则优先保留拥挤距离较大的解，以保持 Pareto 分布均匀：

```text
Archive size <= nd_pool_max
```

项目对应实现：

```text
src/smdfjsp/mvc_eda_ts/archive.py
src/smdfjsp/metrics/multiobjective.py
```

## 11. 跨链协同禁忌搜索

### 11.1 设计动机

EDA 擅长学习全局分布，但对局部微调不足。MVC-SM-DFJSP 的关键局部改进通常发生在：

```text
某些订单是否跨链
跨到哪条价值链
是否把高成本跨链订单回流
是否释放关键 SRU 或关键订单
```

因此局部搜索必须是价值链感知的，不能只做机器替换和工序插入。

### 11.2 六类邻域

当前项目已设计 6 类邻域：

```text
N1_intra_sru_replace
N2_cross_sru_replace
N3_cross_return
N4_critical_cross_migration
N5_high_cost_return
N6_machine_or_os_local
```

#### N1 链内 SRU 替换

将订单从当前 SRU 移动到同一价值链、同一服务类型的其他 SRU。

```text
job j: u_current -> u_intra
```

作用：

```text
在不增加跨链协同成本的情况下改善成本或工期
```

#### N2 跨链 SRU 替换

将订单移动到其他价值链中服务类型匹配的 SRU。

```text
job j: u_current -> u_cross
```

作用：

```text
探索用跨链固定成本换取工期缩短或瓶颈缓解的解
```

该邻域仅在 `cross_chain_allowed = 1` 时启用。

#### N3 跨链回流

将已经跨链的订单迁回其所属价值链内的候选 SRU。

```text
job j: u_cross -> u_intra
```

作用：

```text
降低运输成本和跨链固定协同成本
```

该邻域是成本方向的修正机制，防止算法过度跨链。

#### N4 关键订单跨链迁移

先识别对当前 makespan 贡献较大的关键订单，再将其迁移到预计完成时间更短的跨链 SRU。

```text
critical job j -> fastest cross-chain candidate SRU
```

作用：

```text
直接攻击 F2，提升短工期区域搜索能力
```

#### N5 高成本回流

识别跨链协同成本较高的订单，将其迁回链内 SRU 或成本更低的跨链 SRU。

```text
high-cost cross-chain job j -> cheaper candidate SRU
```

作用：

```text
直接攻击 F1，提升低成本区域搜索能力
```

#### N6 机器或 OS 局部调整

包含两类局部变化：

```text
OS insert: 改变同服务类型内工序排序
machine replace: 改变某道工序的机器选择
```

作用：

```text
在固定 UA 或小幅变动 UA 后细化 SRU 内部调度
```

项目对应实现：

```text
src/smdfjsp/mvc_eda_ts/tabu_search.py
```

### 11.3 禁忌表

对于 SRU 替换类邻域，禁忌属性为：

```text
(move_kind, job_id, from_sru, to_sru)
```

对于 OS 插入类邻域，禁忌属性为：

```text
(move_kind, "os_insert", type_id, job_id, from_pos, to_pos)
```

禁忌长度建议随实例规模变化：

```text
tabu_max_len = sum(min(5, len(OS_type)) for each service type)
```

若候选解支配当前 best 或进入局部非支配集合，可允许破禁。

### 11.4 自适应邻域选择

每类邻域的贡献由三部分构成：

```text
reward_k =
  accepted_k
+ 2 * archive_inserted_k
+ 0.01 * improvement_k
```

归一化后得到目标概率：

```text
target_prob_k = reward_k / sum_k reward_k
```

使用平滑更新：

```text
p_k = (1 - rho) * p_k + rho * target_prob_k
```

当前项目中 `rho = 0.25`。

作用：

```text
如果跨链迁移持续贡献新非支配解，则提高其使用概率；
如果高成本回流持续改善低成本区域，则提高其使用概率；
如果某类邻域长期无贡献，则自然降低采样比例。
```

论文中建议称为：

```text
contribution-based adaptive neighborhood selection
```

不建议正文主打深度强化学习，因为当前项目的数据量、训练集和泛化实验不足以支撑端到端 DRL。自适应邻域选择更稳、更可解释。

## 12. 环境选择与下一代种群

每轮将以下解合并：

```text
new population
local search solutions
archive solutions
```

然后执行非支配排序：

```text
fronts = fast_non_dominated_sort(objectives)
```

优先选择低等级 Pareto front。若最后一个 front 超过剩余容量，则按拥挤距离从大到小选择：

```text
next_pop = rank_by_front_and_crowding(candidates)
```

这样可以兼顾收敛性和分布性。

## 13. 实验设计

### 13.1 实例

建议使用 MVC-MK01 到 MVC-MK15 作为主实验实例。

```text
data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty
data/mvc_mk01_15
data/mvc_la
```

如果论文篇幅允许，可以使用 LA 扩展实例作为泛化补充。

### 13.2 协同模式实验

每个实例至少运行两种模式：

```text
Mode A: cross_chain_allowed = 0
Mode B: cross_chain_allowed = 1
```

Mode A 作为无跨链协同基准，Mode B 用于观察跨链协同是否改善 Pareto 前沿。

### 13.3 对比算法

推荐至少包括：

| 算法 | 作用 |
| --- | --- |
| NSGA-II | 经典多目标进化基线 |
| MOEA/D | 分解式多目标基线 |
| MVC-EDA-TS without prior | 消融价值链先验 |
| MVC-EDA-TS without cross neighborhoods | 消融跨链邻域 |
| MVC-EDA-TS full | 本文算法 |

若实验资源允许，增加：

```text
H-GA-TS
EDA-VNS
```

项目已有相关基线模块：

```text
src/smdfjsp/baselines/mvc_nsgaii.py
src/smdfjsp/baselines/mvc_moead.py
src/smdfjsp/baselines/h_gats.py
src/smdfjsp/baselines/eda.py
src/smdfjsp/baselines/mvc_edats_baseline.py
```

### 13.4 消融实验

消融实验必须做，否则算法创新容易被审稿人认为是增量不足。

建议设置：

| 编号 | 算法变体 | 关闭模块 |
| --- | --- | --- |
| A0 | MVC-EDA-TS full | 无 |
| A1 | w/o VC init | `use_value_chain_init=False` |
| A2 | w/o VC prior | `use_value_chain_prior=False` |
| A3 | w/o cross neighborhoods | `use_cross_chain_neighbors=False` |
| A4 | w/o adaptive neighborhood | `use_adaptive_neighborhood=False` |
| A5 | w/o ND memory | `use_nd_memory=False` |

重点比较：

```text
HV
IGD
ND size
min total_cost
min makespan
cross_chain_ratio
```

预期结论：

```text
价值链先验提升早期收敛速度；
跨链邻域改善短工期区域；
高成本回流和自适应邻域防止过度跨链；
非支配记忆池改善 Pareto 分布和稳定性。
```

### 13.5 敏感性实验

为支撑管理启示，建议做跨链参数敏感性：

```text
cross_fixed_cost: low / medium / high
transport_cost: low / medium / high
cross-chain time advantage: weak / medium / strong
```

分析问题：

1. 什么情况下跨链协同能显著缩短 makespan；
2. 什么情况下跨链成本过高导致跨链不值得；
3. 跨链协同是否会造成某些价值链资源过度流入；
4. 成本和工期折中是否随参数呈现稳定趋势。

### 13.6 评价指标

多目标性能指标：

```text
HV
IGD
GD
Spacing
ND size
Runtime
```

目标值指标：

```text
min_total_cost
min_makespan
average_total_cost_of_ND
average_makespan_of_ND
```

协同诊断指标：

```text
cross_chain_ratio
cross_chain_jobs
intra_chain_jobs
cross_chain_flow
value_chain_inflow
value_chain_outflow
sru_load_std
value_chain_load_std
```

成本拆分指标：

```text
processing_cost
transport_cost
cross_fixed_cost
total_cost
```

### 13.7 统计检验

建议每个算法每个实例独立运行至少 10 次，最好 20 次。统计结果报告：

```text
mean
std
best
rank
```

并使用 Wilcoxon signed-rank test 或 Friedman test 检验算法差异。项目已有统计检验模块：

```text
src/smdfjsp/metrics/stat_tests.py
```

## 14. 结果表和图建议

### 14.1 表 1：符号定义

列出集合、参数、变量。

### 14.2 表 2：算法参数

列出 `popsize`、`max_iter`、`alpha`、`beta`、`gamma`、`prior_weight`、`local_search_steps` 等。

### 14.3 表 3：算法性能对比

按实例报告：

```text
HV, IGD, GD, Spacing, ND size, Runtime
```

### 14.4 表 4：消融实验

展示 A0-A5 各变体的平均指标。

### 14.5 表 5：跨链协同分析

比较 `cross_chain_allowed=0/1`：

```text
min_cost
min_makespan
cross_chain_ratio
sru_load_std
```

### 14.6 图 1：问题结构图

建议画成：

```text
Value chain -> Service type -> SRU -> Machine -> Operation
```

### 14.7 图 2：MVC-EDA-TS 流程图

包含：

```text
initialization -> evaluation -> archive -> probability update -> sampling -> local search -> archive update -> selection
```

### 14.8 图 3：Pareto 前沿图

横轴 total_cost，纵轴 makespan。

比较：

```text
NSGA-II
MOEA/D
MVC-EDA-TS
cross_chain_off
cross_chain_on
```

### 14.9 图 4：跨链流动图

展示：

```text
VC1 -> VC2
VC1 -> VC3
VC2 -> VC1
...
```

### 14.10 图 5：SRU 负载分布

展示允许跨链前后的 SRU 负载变化。

## 15. 代码实现映射

### 15.1 数据与实例

| 功能 | 文件 |
| --- | --- |
| MVC JSON 读写 | `src/smdfjsp/data/mvc_io.py` |
| MVC 实例构造 | `src/smdfjsp/data/mvc_builder.py` |
| MK 数据解析 | `src/smdfjsp/data/mk_parser.py` |
| MVC 类型定义 | `src/smdfjsp/core/mvc_types.py` |

### 15.2 模型与评价

| 功能 | 文件 |
| --- | --- |
| 双目标评价 | `src/smdfjsp/model/mvc_evaluator.py` |
| 可行性修复 | `src/smdfjsp/model/mvc_repair.py` |
| 四层编码 | `src/smdfjsp/core/encoding.py` |

### 15.3 算法

| 功能 | 文件 |
| --- | --- |
| MVC-EDA-TS 主流程 | `src/smdfjsp/mvc_eda_ts/algorithm.py` |
| 价值链先验概率模型 | `src/smdfjsp/mvc_eda_ts/probability_model.py` |
| 启发式初始化 | `src/smdfjsp/mvc_eda_ts/initialization.py` |
| 跨链禁忌搜索邻域 | `src/smdfjsp/mvc_eda_ts/tabu_search.py` |
| 非支配档案 | `src/smdfjsp/mvc_eda_ts/archive.py` |

### 15.4 对比算法

| 功能 | 文件 |
| --- | --- |
| MVC NSGA-II | `src/smdfjsp/baselines/mvc_nsgaii.py` |
| MVC MOEA/D | `src/smdfjsp/baselines/mvc_moead.py` |
| H-GA-TS | `src/smdfjsp/baselines/h_gats.py` |
| EDA / EDA-VNS | `src/smdfjsp/baselines/eda.py` |

### 15.5 指标与图

| 功能 | 文件 |
| --- | --- |
| HV/IGD/GD/Spacing | `src/smdfjsp/metrics/multiobjective.py` |
| 性能指标兼容模块 | `src/smdfjsp/metrics/performance.py` |
| 统计检验 | `src/smdfjsp/metrics/stat_tests.py` |
| 可视化 | `src/smdfjsp/visualization/mvc_plots.py` |

## 16. 论文方法章节建议结构

建议第 4 节算法章节按如下结构写：

```text
4. Proposed MVC-EDA-TS
4.1 Four-layer encoding and decoding
4.2 Value-chain-aware initialization
4.3 Value-chain prior probability model
4.4 Non-dominated archive
4.5 Cross-chain collaborative tabu search
4.6 Adaptive neighborhood selection
4.7 Overall algorithm and complexity discussion
```

其中 4.3 和 4.5 是算法创新重点。

## 17. 论文实验章节建议结构

建议第 5 节实验按如下结构写：

```text
5. Computational Experiments
5.1 Instance construction
5.2 Compared algorithms and parameter settings
5.3 Performance metrics
5.4 Overall comparison
5.5 Ablation study
5.6 Intra-chain vs cross-chain collaboration analysis
5.7 Sensitivity analysis
5.8 Managerial implications
```

其中 5.6 和 5.8 是区分普通算法论文和共享制造协同论文的关键。

## 18. 审稿风险与补强措施

### 18.1 风险一：价值链层被认为只是标签

补强方式：

1. 给出链内/跨链候选集定义；
2. 给出跨链固定协同成本定义；
3. 给出不允许跨链/允许跨链对比实验；
4. 给出跨链流动和成本拆分分析；
5. 给出小型说明例子，证明同服务类型 SRU 因价值链归属不同而产生不同调度后果。

### 18.2 风险二：算法创新被认为只是 EDA-TS 小改

补强方式：

1. 明确价值链先验概率模型；
2. 明确 6 类跨链协同邻域；
3. 做完整消融实验；
4. 报告邻域贡献统计；
5. 报告开启/关闭先验时的收敛曲线。

### 18.3 风险三：实验不足

补强方式：

1. 至少 MVC-MK01 到 MVC-MK15；
2. 每实例至少 10 次独立运行；
3. 与 NSGA-II、MOEA/D、原始/弱化 EDA-TS 对比；
4. 使用 HV、IGD、Spacing、ND size；
5. 使用统计检验。

### 18.4 风险四：成本参数人为性强

补强方式：

1. 说明参数生成规则；
2. 固定随机种子；
3. 做跨链固定成本敏感性；
4. 做运输成本敏感性；
5. 做跨链加工时间优势敏感性。

### 18.5 风险五：双目标/三目标口径混乱

补强方式：

1. 正文正式模型只写双目标；
2. 三目标作为未来工作；
3. 负载指标只用于诊断；
4. 代码中 `objective_dim=2` 作为主实验默认设置。

## 19. 推荐真实有效参考文献

以下文献建议优先放入相关工作和方法依据中。引用时请按目标期刊格式转换。

1. Wei 等，2024，Shared manufacturing-based distributed flexible job shop scheduling with supply-demand matching，Computers & Industrial Engineering，DOI: 10.1016/j.cie.2024.109950。

2. De Giovanni and Pezzella，2010，An improved genetic algorithm for the distributed and flexible job-shop scheduling problem，European Journal of Operational Research，DOI: 10.1016/j.ejor.2009.01.008。

3. Luo 等，2020，Distributed flexible job shop scheduling problem with transfers，Expert Systems with Applications，DOI: 10.1016/j.eswa.2020.113721。

4. Du 等，2021，A hybrid estimation of distribution algorithm for distributed flexible job shop scheduling with crane transportations，Swarm and Evolutionary Computation，DOI: 10.1016/j.swevo.2021.100861。

5. Xie 等，2023，A hybrid genetic tabu search algorithm for distributed flexible job shop scheduling，Journal of Manufacturing Systems，DOI: 10.1016/j.jmsy.2023.09.002。

6. Dauzere-Peres 等，2024，The flexible job shop scheduling problem: A review，European Journal of Operational Research，DOI: 10.1016/j.ejor.2023.05.017。

7. Zhang 等，2024，A learning-driven multi-objective cooperative artificial bee colony algorithm for distributed flexible job shop scheduling with preventive maintenance and transportation operations，Computers & Industrial Engineering，DOI: 10.1016/j.cie.2024.110484。

8. Multi-objective fitness landscape-based estimation of distribution algorithm for distributed heterogeneous flexible job shop scheduling problem，2025，Applied Soft Computing，DOI: 10.1016/j.asoc.2025.112780。

9. Co-Evolutionary NSGA-III with deep reinforcement learning for multi-objective distributed flexible job shop scheduling，2025，Computers & Industrial Engineering，DOI: 10.1016/j.cie.2025.110990。

10. Xiong and Liu，2025，Logic-based Benders decomposition for distributed flexible job shop scheduling，European Journal of Operational Research，DOI: 10.1016/j.ejor.2025.08.039。

## 20. 最终推荐实施路线

当前项目最适合按以下顺序推进：

```text
Step 1: 固化双目标口径
Step 2: 检查 total_cost = processing + transport + cross_fixed
Step 3: 跑通 MVC-MK01 到 MVC-MK15
Step 4: 跑 cross_chain_allowed=0/1 对比
Step 5: 跑 NSGA-II、MOEA/D、MVC-EDA-TS full
Step 6: 跑 A1-A5 消融
Step 7: 汇总 HV/IGD/Spacing/ND size
Step 8: 汇总 cross_chain_ratio、flow、load、cost breakdown
Step 9: 做跨链成本敏感性
Step 10: 根据结果回写论文结论和管理启示
```

如果时间有限，最低可接受实验闭环为：

```text
MVC-MK01 到 MVC-MK15
3 个算法：NSGA-II, MOEA/D, MVC-EDA-TS
2 个模式：cross_chain_off, cross_chain_on
3 个随机种子
4 个指标：HV, IGD, min_cost, min_makespan
1 个消融：关闭价值链先验、关闭跨链邻域
```

但正式投稿建议扩大到 10 个以上随机种子，并增加统计检验。

## 21. 一句话论文主线

本文面向多服务价值链共享制造平台，提出 MVC-SM-DFJSP 双目标调度问题，显式区分订单价值链归属与制造服务类型需求，并通过价值链感知概率模型、跨链协同禁忌搜索邻域和非支配记忆池构建 MVC-EDA-TS，以获得成本和工期之间可解释的 Pareto 折中，同时揭示链内/跨链资源协同对共享制造平台调度性能的影响。
