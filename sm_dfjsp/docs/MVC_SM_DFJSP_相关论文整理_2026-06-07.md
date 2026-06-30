# MVC-SM-DFJSP 相关论文整理

创建日期：2026-06-07  
主题：分布式柔性作业车间调度、共享制造、多目标优化、EDA-TS、跨链/跨工厂协同、学习增强启发式  
用途：支撑“面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度”论文的相关工作、方法依据和参考文献筛选。

## 1. 文献使用建议

本文献整理服务于当前项目的双目标论文主线：

```text
MVC-SM-DFJSP:
job -> value chain ownership
    -> service type matching
    -> intra-chain/cross-chain SRU selection
    -> machine selection
    -> operation sequencing

Objectives:
min total_cost
min makespan
```

建议将相关工作分成 5 类来写：

1. 柔性作业车间与分布式柔性作业车间调度；
2. 共享制造、云制造与供需匹配；
3. 跨工厂转运、运输、维护和复杂约束扩展；
4. 多目标元启发式、EDA、TS、VNS 和 memetic algorithm；
5. 学习增强、强化学习和图模型前沿方法。

当前论文最核心的引用链应为：

```text
FJSP/DFJSP 经典与综述
-> 共享制造 SM-DFJSP with supply-demand matching
-> EDA/VNS/TS 等问题知识驱动算法
-> 学习增强和图强化方法作为前沿对照
-> 本文 MVC-SM-DFJSP 的价值链协同扩展
```

## 2. 核心必读文献

### 2.1 Shared manufacturing-based distributed flexible job shop scheduling with supply-demand matching

- 年份：2024
- 期刊：Computers & Industrial Engineering
- DOI：10.1016/j.cie.2024.109950
- 链接：https://doi.org/10.1016/j.cie.2024.109950
- 主题：共享制造、供需匹配、SM-DFJSP、双目标、EDA-TS
- 与本文关系：这是当前项目最直接的基础文献。该文在共享制造场景下提出 SM-DFJSP，将制造资源抽象为 SRU，并以总成本和最大完工时间为目标，采用 EDA-TS 求解。
- 本文可借鉴：
  - SRU 作为共享制造资源单元的抽象方式；
  - 服务类型供需匹配机制；
  - `total_cost` 和 `makespan` 双目标设置；
  - EDA-TS 框架、概率模型和非支配记忆机制。
- 本文需要区别：
  - 该文主要是“服务类型-SRU-机器”结构；
  - 本文扩展为“价值链-服务类型-SRU-机器”结构；
  - 本文显式区分订单价值链归属与制造服务类型需求；
  - 本文引入链内/跨链 SRU 选择和跨链固定协同成本。

### 2.2 An Improved Genetic Algorithm for the Distributed and Flexible Job-shop Scheduling problem

- 年份：2010
- 期刊：European Journal of Operational Research
- DOI：10.1016/j.ejor.2009.01.008
- 链接：https://doi.org/10.1016/j.ejor.2009.01.008
- 主题：DFJSP、分布式柔性作业车间、工厂分配、机器选择、工序排序、遗传算法
- 与本文关系：DFJSP 经典基础文献之一，定义了分布式柔性作业车间中作业分配与车间内调度的耦合结构。
- 本文可借鉴：
  - 分布式制造环境中的作业到制造单元分配；
  - 柔性制造单元内部机器选择；
  - 多层编码思想。
- 本文需要区别：
  - 该文以分布式 FMU/工厂为主；
  - 本文将制造单元解释为共享制造中的 SRU；
  - 本文额外考虑价值链归属、服务类型匹配和跨链协同成本。

### 2.3 The flexible job shop scheduling problem: A review

- 年份：2024
- 期刊：European Journal of Operational Research
- DOI：10.1016/j.ejor.2023.05.017
- 链接：https://doi.org/10.1016/j.ejor.2023.05.017
- 主题：FJSP 综述、多目标、复杂约束、动态环境、求解方法
- 与本文关系：用于相关工作开头，说明 FJSP 是 NP-hard 组合优化问题，并且已经扩展到多目标、动态、不确定、复杂约束和分布式制造等方向。
- 本文可借鉴：
  - FJSP 研究分类；
  - 多目标优化和复杂约束扩展的综述口径；
  - 将本文问题定位为 FJSP/DFJSP 在共享制造价值链协同下的新扩展。

## 3. 共享制造、云制造与供需匹配

### 3.1 Planning and scheduling shared manufacturing systems: key characteristics, current developments and future trends

- 年份：2025
- 期刊：International Journal of Production Research
- DOI：10.1080/00207543.2024.2442549
- 链接：https://doi.org/10.1080/00207543.2024.2442549
- 主题：共享制造系统、规划与调度、共享产能、P2P 协同、未来趋势
- 与本文关系：可用于引言和相关工作，支撑共享制造调度问题的现实背景。
- 本文可借鉴：
  - 共享制造作为服务化、平台化、协同化制造范式；
  - 共享制造规划和调度涉及成本、时间、资源利用、协同关系；
  - 当前共享制造调度研究仍需要更细粒度的资源协同模型。
- 本文需要区别：
  - 该文是综述；
  - 本文提出具体的 MVC-SM-DFJSP 模型与求解算法。

### 3.2 Scheduling in cloud manufacturing: state-of-the-art and research challenges

- 年份：2019
- 期刊：International Journal of Production Research
- DOI：10.1080/00207543.2018.1449978
- 链接：https://doi.org/10.1080/00207543.2018.1449978
- 主题：云制造调度、服务组合、任务-资源匹配、多目标、多约束
- 与本文关系：可用于解释共享制造与云制造中的服务组合、服务匹配和资源调度问题。
- 本文可借鉴：
  - 制造服务组合本质上是多目标、多约束、NP-hard 的组合优化问题；
  - 制造任务与服务资源之间存在多粒度匹配；
  - 平台化制造环境下调度需要同时考虑资源选择和执行过程。
- 本文需要区别：
  - 云制造文献多侧重服务组合和 QoS；
  - 本文进一步落到 SRU 内部柔性作业车间调度过程。

### 3.3 Topology analysis of manufacturing service supply-demand hyper-network considering QoS properties in the cloud manufacturing system

- 年份：2021
- 期刊：Robotics and Computer-Integrated Manufacturing
- DOI：10.1016/j.rcim.2021.102205
- 链接：https://doi.org/10.1016/j.rcim.2021.102205
- 主题：云制造、制造服务供需匹配、QoS、超网络
- 与本文关系：可用于支撑“供需匹配是服务化制造平台中的关键问题”。
- 本文可借鉴：
  - 供给侧制造服务与需求侧订单之间的匹配关系；
  - QoS 或成本/时间等属性对匹配决策的影响。
- 本文需要区别：
  - 该文偏网络拓扑和服务匹配分析；
  - 本文把匹配后的资源选择与作业车间排程统一建模。

### 3.4 An information freshness-based digital twin model to support multi-level complementary dynamic scheduling in Shared Manufacturing

- 年份：2024
- 期刊：Advanced Engineering Informatics
- DOI：10.1016/j.aei.2024.102525
- 链接：https://doi.org/10.1016/j.aei.2024.102525
- 主题：共享制造、数字孪生、动态调度、多层互补调度
- 与本文关系：可作为共享制造动态调度和多层协同的前沿参考。
- 本文可借鉴：
  - 共享制造调度不仅涉及制造服务，还可能涉及运输和多层资源协同；
  - 共享制造开放环境下扰动和重调度重要。
- 本文需要区别：
  - 当前论文聚焦静态双目标 MVC-SM-DFJSP；
  - 动态重调度可放在未来工作。

## 4. DFJSP、转运与复杂约束扩展

### 4.1 An efficient memetic algorithm for distributed flexible job shop scheduling problem with transfers

- 年份：2020
- 期刊：Expert Systems with Applications
- DOI：10.1016/j.eswa.2020.113721
- 链接：https://doi.org/10.1016/j.eswa.2020.113721
- 主题：DFJSP with transfers、跨工厂转运、memetic algorithm、初始化、邻域结构
- 与本文关系：本文的跨链 SRU 选择与该文的跨工厂转运有相似之处，都突破了传统“一个作业固定在一个工厂/资源单元完成”的限制。
- 本文可借鉴：
  - 转运会显著扩大解空间；
  - 问题特定初始化和邻域结构比通用遗传算子更有效；
  - 跨资源单元协同需要在模型和算法中同时处理。
- 本文需要区别：
  - 该文关注工序可跨工厂转运；
  - 本文当前设定是订单分配到一个 SRU，并比较链内/跨链 SRU 选择；
  - 本文跨链强调价值链归属和固定协同成本。

### 4.2 Hybrid Memetic Algorithm to Solve Multiobjective Distributed Fuzzy Flexible Job Shop Scheduling Problem with Transfer

- 年份：2022
- 期刊：Processes
- DOI：10.3390/pr10081517
- 链接：https://doi.org/10.3390/pr10081517
- 主题：多目标、分布式模糊柔性作业车间、转运、memetic algorithm
- 与本文关系：可作为多目标 DFJSPT 和不确定加工环境的扩展参考。
- 本文可借鉴：
  - 多目标转运场景下的 Pareto 优化；
  - 复杂约束会强化问题特定局部搜索的重要性。
- 本文需要区别：
  - 该文考虑模糊加工时间；
  - 本文当前先保持确定性双目标，以提高模型和实验闭环稳定性。

### 4.3 A learning-driven multi-objective cooperative artificial bee colony algorithm for distributed flexible job shop scheduling problems with preventive maintenance and transportation operations

- 年份：2024
- 期刊：Computers & Industrial Engineering
- DOI：10.1016/j.cie.2024.110484
- 链接：https://doi.org/10.1016/j.cie.2024.110484
- 主题：DFJSP、预防性维护、运输、多目标、学习驱动协同人工蜂群算法
- 与本文关系：可用于支撑“学习驱动/自适应算子选择”在复杂 DFJSP 中有效。
- 本文可借鉴：
  - 运输操作和维护操作可与分布式车间调度联合建模；
  - 学习机制可用于改善多目标启发式搜索。
- 本文需要区别：
  - 该文关注维护和运输；
  - 本文关注价值链归属、跨链协同和 SRU 共享。

### 4.4 Dynamic distributed flexible job-shop scheduling problem considering operation inspection

- 年份：2023
- 期刊：Expert Systems with Applications
- DOI：10.1016/j.eswa.2023.119753
- 链接：https://doi.org/10.1016/j.eswa.2023.119753
- 主题：动态 DFJSP、工序检验、动态事件、智能调度
- 与本文关系：可作为动态扩展和未来工作参考。
- 本文可借鉴：
  - DFJSP 正在从静态调度扩展到动态扰动和工序级约束；
  - 当前论文可在结论中提出动态订单到达、设备故障、质量检验作为未来方向。

## 5. EDA、TS、VNS 与问题知识驱动算法

### 5.1 A hybrid estimation of distribution algorithm for distributed flexible job shop scheduling with crane transportations

- 年份：2021
- 期刊：Swarm and Evolutionary Computation
- DOI：10.1016/j.swevo.2021.100861
- 链接：https://doi.org/10.1016/j.swevo.2021.100861
- 主题：DFJSP、起重运输、双目标、EDA-VNS、自适应概率、问题特定邻域
- 与本文关系：非常适合支撑 MVC-EDA-TS 中“概率模型 + 局部搜索”的算法路线。
- 本文可借鉴：
  - EDA 适合学习分布式调度的多层决策结构；
  - VNS/局部搜索可利用问题特定邻域强化 exploitation；
  - 复杂运输约束需要专门设计可行性识别和邻域结构。
- 本文需要区别：
  - 该文关注起重运输与能耗；
  - 本文关注跨价值链 SRU 协同和成本-工期折中。

### 5.2 A hybrid genetic tabu search algorithm for distributed flexible job shop scheduling problems

- 年份：2023
- 期刊：Journal of Manufacturing Systems
- DOI：10.1016/j.jmsy.2023.09.002
- 链接：https://doi.org/10.1016/j.jmsy.2023.09.002
- 主题：DFJSP、GA、Tabu Search、混合启发式、强基线
- 与本文关系：适合作为对比算法或强基线思想来源。
- 本文可借鉴：
  - TS 对 DFJSP 局部强化有效；
  - GA/TS 混合框架可作为大规模组合调度的强竞争算法。
- 本文需要区别：
  - 本文不是单纯 GA-TS；
  - 本文将 EDA 概率学习与价值链先验、跨链邻域结合。

### 5.3 Multi-objective fitness landscape-based estimation of distribution algorithm for distributed heterogeneous flexible job shop scheduling problem

- 年份：2025
- 期刊：Applied Soft Computing
- DOI：10.1016/j.asoc.2025.112780
- 链接：https://doi.org/10.1016/j.asoc.2025.112780
- 主题：分布式异构 FJSP、序列相关准备时间、多目标、fitness landscape、EDA、自适应局部搜索
- 与本文关系：这是支撑“问题知识驱动 EDA”和“自适应局部搜索”的重要前沿文献。
- 本文可借鉴：
  - 仅依赖精英频率的 EDA 可能早熟；
  - 将问题知识注入概率模型和局部搜索选择可以提升搜索质量；
  - 多目标景观/贡献信息可用于指导局部搜索算子选择。
- 本文需要区别：
  - 该文的问题知识来自 fitness landscape 和异构工厂特征；
  - 本文的问题知识来自价值链归属、跨链成本、服务类型匹配和跨链时间收益。

### 5.4 A self-learning multi-population evolutionary algorithm for flexible job shop scheduling under time-of-use pricing

- 年份：2024
- 期刊：Computers & Industrial Engineering
- DOI：10.1016/j.cie.2024.110004
- 链接：https://doi.org/10.1016/j.cie.2024.110004
- 主题：FJSP、分时电价、多种群、自学习、成本与工期
- 与本文关系：可用于说明自学习或自适应机制在成本-工期类调度中有效。
- 本文可借鉴：
  - 多种群和自学习机制可兼顾探索与开发；
  - 成本目标与工期目标冲突时，需要保持解集多样性。
- 本文需要区别：
  - 该文关注能源成本；
  - 本文关注共享制造中的运输成本和跨链固定协同成本。

## 6. 学习增强、强化学习与图模型前沿

### 6.1 Co-Evolutionary NSGA-III with deep reinforcement learning for multi-objective distributed flexible job shop scheduling

- 年份：2025
- 期刊：Computers & Industrial Engineering
- DOI：10.1016/j.cie.2025.110990
- 链接：https://doi.org/10.1016/j.cie.2025.110990
- 主题：MO-DFJSP、NSGA-III、深度强化学习、协同进化、碳排放
- 与本文关系：可作为前沿方法参考，说明 DRL 已被用于多目标 DFJSP。
- 本文可借鉴：
  - 强化学习可用于与进化算法协同；
  - 多目标分布式调度越来越关注效率、交期和环境目标。
- 本文需要区别：
  - 本文当前不建议主打端到端 DRL；
  - 当前项目更适合问题知识驱动的 MVC-EDA-TS；
  - DRL 可作为未来工作或高级对比方向。

### 6.2 Graph-based reinforced multi-objective optimization for distributed heterogeneous flexible job shop scheduling problem under nonidentical time-of-use electricity tariffs

- 年份：2025
- 期刊：Expert Systems with Applications
- DOI：10.1016/j.eswa.2025.128428
- 链接：https://doi.org/10.1016/j.eswa.2025.128428
- 主题：分布式异构 FJSP、图神经网络、强化学习、PPO、自适应算子选择、分时电价
- 与本文关系：可作为“图结构 + 强化学习 + 自适应算子选择”的前沿参考。
- 本文可借鉴：
  - GNN 可编码复杂调度结构；
  - PPO 等强化学习方法可用于选择局部搜索算子；
  - 复杂分布式调度需要结合模型、知识邻域和学习机制。
- 本文需要区别：
  - 本文目前不构建 GNN 状态表示；
  - 本文使用贡献驱动的轻量自适应邻域选择，优点是可解释、易复现、实验成本低。

### 6.3 Deep reinforcement learning driven trajectory-based meta-heuristic for distributed heterogeneous flexible job shop scheduling problem

- 年份：2024
- 期刊：Swarm and Evolutionary Computation
- DOI：10.1016/j.swevo.2024.101753
- 链接：https://doi.org/10.1016/j.swevo.2024.101753
- 主题：DHFJSP、DQN、VNS、轨迹型元启发式、自动策略设计
- 与本文关系：可作为 DQN 辅助局部搜索/邻域选择的前沿参考。
- 本文可借鉴：
  - DQN 可用于从特征状态中选择 shaking/local search 策略；
  - 学习增强更适合作为复杂元启发式的控制层，而不是完全替代启发式。
- 本文需要区别：
  - 本文当前用自适应贡献奖励选择邻域；
  - 后续可扩展为 Q-learning 或 DQN 邻域选择。

### 6.4 A twin-reinforced evolutionary algorithm for flexible job shop scheduling problem under time-of-use tariffs

- 年份：2026
- 期刊：Computers & Industrial Engineering
- DOI：10.1016/j.cie.2025.111754
- 链接：https://doi.org/10.1016/j.cie.2025.111754
- 主题：FJSP、分时电价、Q-learning、算子选择、进化算法
- 与本文关系：可作为强化学习指导算子选择的最新参考之一。
- 本文可借鉴：
  - Q-learning 可用于局部搜索算子选择；
  - 学习机制可嵌入元启发式内部，而不必完全重构调度模型。
- 本文需要区别：
  - 该文关注分时电价；
  - 本文关注跨链固定协同成本和共享制造价值链协同。

### 6.5 A Solution Space Transformation-Guided Co-Evolution for Energy-Saving Distributed Heterogeneous Flexible Job Shop Scheduling

- 年份：2026
- 会议：AAAI
- 链接：https://ojs.aaai.org/index.php/AAAI/article/view/41033
- 主题：分布式异构 FJSP、节能、解空间变换、协同进化
- 与本文关系：可作为大规模分布式异构 FJSP 的前沿参考。
- 本文可借鉴：
  - 解空间变换和问题结构利用是近年来的重要趋势；
  - 复杂分布式调度不应只依赖通用交叉变异。
- 本文需要区别：
  - 本文当前采用价值链先验和跨链邻域来缩小/引导搜索空间；
  - 该方向可作为未来算法增强方向。

## 7. Industry 5.0、绿色与韧性调度综述

### 7.1 Flexible job shop scheduling problem under Industry 5.0: A survey on human reintegration, environmental consideration and resilience improvement

- 年份：2023
- 期刊：Journal of Manufacturing Systems
- DOI：10.1016/j.jmsy.2023.01.004
- 链接：https://doi.org/10.1016/j.jmsy.2023.01.004
- 主题：Industry 5.0、FJSP、以人为中心、环境、韧性
- 与本文关系：可用于引言中说明现代 FJSP 正向可持续、韧性和复杂生产环境扩展。
- 本文可借鉴：
  - 调度目标从单一 makespan 扩展到成本、能源、韧性、人因等多目标；
  - 生产调度需要服务于现实生产系统的复杂管理目标。
- 本文需要区别：
  - 本文不做人因和绿色目标；
  - 本文侧重共享制造平台价值链协同。

### 7.2 From human-related to human-centric: A review of shop floor scheduling problem under Industry 5.0

- 年份：2025
- 期刊：Journal of Manufacturing Systems
- DOI：10.1016/j.jmsy.2025.07.003
- 链接：https://doi.org/10.1016/j.jmsy.2025.07.003
- 主题：Industry 5.0、以人为中心的车间调度、综述
- 与本文关系：可作为未来工作或扩展背景引用。
- 本文可借鉴：
  - 车间调度正从单纯效率优化走向多主体、多目标和韧性优化；
  - 共享制造平台中的多价值链协同也属于多主体协同的一种表现。

## 8. 精确算法与小规模验证参考

### 8.1 Logic-based Benders decomposition for distributed flexible job shop scheduling

- 年份：2025
- 期刊：European Journal of Operational Research
- DOI：10.1016/j.ejor.2025.08.039
- 链接：https://doi.org/10.1016/j.ejor.2025.08.039
- 主题：DFJSP、logic-based Benders decomposition、精确/分解方法
- 与本文关系：可用于说明小规模实例可用精确算法或分解算法验证模型合理性。
- 本文可借鉴：
  - 对小规模 MVC-SM-DFJSP 可考虑建立 MILP/Gurobi 或分解模型作为验证；
  - 大规模实例仍依赖启发式/元启发式。
- 本文需要区别：
  - 当前项目主线是 MVC-EDA-TS；
  - 精确算法可作为小规模验证，不作为主求解器。

## 9. 建议放入论文相关工作的逻辑顺序

### 9.1 第一段：FJSP 和 DFJSP 基础

可引用：

```text
De Giovanni and Pezzella, 2010
Dauzere-Peres et al., 2024
```

建议写法：

```text
FJSP extends classical job shop scheduling by allowing operations to be processed on alternative machines, while DFJSP further introduces distributed manufacturing units and couples job-to-unit assignment with intra-unit routing and sequencing decisions.
```

### 9.2 第二段：共享制造与供需匹配

可引用：

```text
Scheduling in cloud manufacturing, 2019
Planning and scheduling shared manufacturing systems, 2025
SM-DFJSP with supply-demand matching, 2024
```

建议写法：

```text
Shared manufacturing and cloud manufacturing transform manufacturing resources into service-oriented capacities. Existing studies have addressed manufacturing service matching and resource scheduling, but most models do not distinguish business value-chain ownership from manufacturing service type requirements.
```

### 9.3 第三段：跨资源协同、运输和转运

可引用：

```text
DFJSP with transfers, 2020
DFJSP with crane transportations, 2021
L-MCABC with transportation operations, 2024
```

建议写法：

```text
Recent DFJSP extensions consider transfers, transportation, maintenance and other realistic constraints, showing that distributed scheduling must jointly optimize resource assignment and inter-resource collaboration costs.
```

### 9.4 第四段：多目标元启发式与 EDA/TS

可引用：

```text
Hybrid EDA for crane transportations, 2021
H-GA-TS for DFJSP, 2023
MFLEDA, 2025
SM-DFJSP EDA-TS, 2024
```

建议写法：

```text
Hybrid metaheuristics combining probabilistic model learning and problem-specific local search have shown strong performance in DFJSP. However, existing algorithms do not explicitly learn value-chain collaboration patterns or design neighborhoods for intra-chain/cross-chain SRU migration.
```

### 9.5 第五段：学习增强前沿

可引用：

```text
CEGA-DRL, 2025
GRMO, 2025
DQN-VNS, 2024
Twin-reinforced EA, 2026
```

建议写法：

```text
Learning-enhanced scheduling methods, including reinforcement learning and graph-based representation, have recently been used to guide operator selection and decision making. Inspired by this trend, this study adopts a lightweight contribution-based adaptive neighborhood mechanism rather than a data-hungry end-to-end DRL framework, preserving interpretability and reproducibility for the proposed value-chain-aware scheduling problem.
```

## 10. 与当前论文最推荐引用的文献组合

如果篇幅有限，至少引用以下 10 篇：

1. De Giovanni and Pezzella, 2010, EJOR, DOI: 10.1016/j.ejor.2009.01.008。
2. Dauzere-Peres et al., 2024, EJOR, DOI: 10.1016/j.ejor.2023.05.017。
3. Scheduling in cloud manufacturing, 2019, IJPR, DOI: 10.1080/00207543.2018.1449978。
4. Planning and scheduling shared manufacturing systems, 2025, IJPR, DOI: 10.1080/00207543.2024.2442549。
5. Shared manufacturing-based DFJSP with supply-demand matching, 2024, CIE, DOI: 10.1016/j.cie.2024.109950。
6. DFJSP with transfers, 2020, ESWA, DOI: 10.1016/j.eswa.2020.113721。
7. Hybrid EDA for DFJSP with crane transportations, 2021, SWEVO, DOI: 10.1016/j.swevo.2021.100861。
8. H-GA-TS for DFJSP, 2023, JMS, DOI: 10.1016/j.jmsy.2023.09.002。
9. MFLEDA for DHFJSP, 2025, ASOC, DOI: 10.1016/j.asoc.2025.112780。
10. Learning-driven multi-objective ABC for DFJSP with maintenance and transportation, 2024, CIE, DOI: 10.1016/j.cie.2024.110484。

如果希望体现前沿性，再加入：

```text
CEGA-DRL, 2025, DOI: 10.1016/j.cie.2025.110990
GRMO, 2025, DOI: 10.1016/j.eswa.2025.128428
DQN-VNS, 2024, DOI: 10.1016/j.swevo.2024.101753
```

## 11. 当前论文的文献缺口表述

建议在相关工作末尾写出如下研究缺口：

```text
Although existing studies have investigated DFJSP, SM-DFJSP, transportation-aware DFJSP and learning-enhanced multi-objective scheduling, three gaps remain.

First, shared manufacturing scheduling studies mainly match manufacturing service types and resource capabilities, while the business value-chain ownership of orders is rarely distinguished from their service type requirements.

Second, existing DFJSP transfer and transportation models describe cross-factory movement or logistics operations, but they do not model intra-chain and cross-chain collaboration costs among multiple service value chains in a shared manufacturing platform.

Third, existing EDA-TS or memetic algorithms usually design probability models and neighborhoods for factory assignment, machine selection and operation sequencing, but they do not learn value-chain-aware SRU assignment patterns or design local search neighborhoods for cross-chain migration and return.

To fill these gaps, this study proposes MVC-SM-DFJSP and develops a value-chain-aware MVC-EDA-TS algorithm for the bi-objective optimization of total cost and makespan.
```

## 12. 投稿前核对清单

正式投稿前建议完成：

1. 用 Zotero、EndNote 或期刊 BibTeX 从 DOI 自动导出作者、卷期页码；
2. 检查所有 DOI 是否能解析到出版社页；
3. 确认文中引用和参考文献列表一一对应；
4. 避免引用过多泛泛综述，核心应集中在 SM-DFJSP、DFJSP、EDA/TS 和共享制造；
5. 对 2025-2026 前沿学习方法保持“参考/未来工作”定位，不把当前论文包装成深度强化学习论文。

