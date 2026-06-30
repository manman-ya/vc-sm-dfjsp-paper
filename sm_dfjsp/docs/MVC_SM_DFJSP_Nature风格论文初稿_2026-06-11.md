# 面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度方法

> Nature-style manuscript draft, Chinese version.  
> Draft date: 2026-06-11.  
> Evidence boundary: this draft is written from the current project documents, code and generated results. The formal main experiment covers MVC-MK01 to MVC-MK15, three algorithms, two cross-chain modes and five random seeds under a two-objective setting. A separate Plain EDA-TS baseline was run in cross-off mode and merged into the statistical comparison. Small-scale exact validation has been completed on three enumerable MVC-SM-DFJSP instances under cross-off and cross-on modes. The integrated-mechanism equal-processing medium experiment covers 15 mechanism instances, two random seeds, four cross-off algorithms and MVC-EDA-TS off/on comparison under popsize 50 and max_iter 50; it is used as mechanism evidence rather than a replacement for the formal equal-processing benchmark. The focused mk14/mk15 mechanism-case experiment covers cross-time-advantage and intra-congested scenarios under popsize 80, max_iter 150 and five seeds, and is used to compare two different activation mechanisms for cross-chain scheduling. The ablation and sensitivity analyses remain lightweight; the available sensitivity summaries in the 2026-06-15 result folder cover mk05 only. Final reference verification remains to be completed.

## 题名

面向多服务价值链协同的共享制造分布式柔性作业车间双目标调度方法

## 英文题名

Value-chain-aware bi-objective scheduling for shared-manufacturing distributed flexible job shops

## 摘要

共享制造平台正在把分散的制造资源组织成可调用、可组合、可协同的服务网络。现有共享制造调度研究通常关注订单服务类型与制造资源能力之间的供需匹配，但较少区分订单所属业务价值链与订单所需制造服务类型这两个层面。当多个服务价值链同时接入平台时，同一类制造服务既可以由链内资源完成，也可以由其他价值链的开放资源协同完成。前者通常具有较低协调成本，后者可能缩短工期或释放瓶颈，但会引入额外运输和跨链协调成本。如何在价值链归属、服务类型匹配、服务资源单元选择和车间内部排程之间建立统一模型，是共享制造调度走向多链协同的关键问题。

本文提出多服务价值链协同共享制造分布式柔性作业车间调度问题（MVC-SM-DFJSP）。该问题在共享制造分布式柔性作业车间调度的“服务类型-SRU-机器”结构上引入订单级价值链归属，形成“价值链-服务类型-SRU-机器”的层级调度机制。本文以总成本和最大完工时间为优化目标，将加工成本、运输成本和跨链固定协调成本纳入统一评价，并将跨链比例、价值链流入流出和 SRU 负载分布作为协同诊断指标。为求解该问题，本文设计价值链感知 MVC-EDA-TS 算法，在估计分布算法和禁忌搜索框架中嵌入价值链先验、链内/跨链 SRU 替换、跨链回流、关键订单迁移、成本回流、自适应邻域选择和非支配解档案。

基于 MK/FJSP benchmark，本文构造了 15 个 MVC-MK 扩展实例，并在种群规模 80、最大迭代 150、5 个随机种子的设置下比较 MVC-EDA-TS、NSGA-II、MOEA/D 和 Plain EDA-TS。为验证模型和解码器一致性，本文另构造 3 个可穷举小规模 MVC-SM-DFJSP 实例；在 cross-off 与 cross-on 的 6 个组合中，MVC-EDA-TS 均恢复真实非支配前沿，且未产生不可行解或伪非支配解。统一统计口径下，MVC-EDA-TS-off 的平均 HV 为 \(2.348\times10^7\)，平均 IGD 为 \(1.429\times10^4\)，平均最低总成本为 \(1.538\times10^4\)，平均最短最大完工时间为 158.5，均优于三个 cross-off 基线。Wilcoxon signed-rank tests 显示，MVC-EDA-TS-off 相对 NSGA-II-off、MOEA/D-off 和 Plain EDA-TS-off 在 HV、IGD、最低总成本和最短最大完工时间上均达到显著优势；Friedman ranking 也将 MVC-EDA-TS 排为四项指标第一。Plain EDA-TS 在 IGD 和最低总成本上优于 NSGA-II 与 MOEA/D，但在 HV 上没有显著优势且最短最大完工时间显著较差。跨链协同的总体收益具有实例依赖性：MVC-EDA-TS-on 相对 MVC-EDA-TS-off 的 HV 和最短最大完工时间仅小幅变化，敏感性实验进一步表明，只有当跨链资源具有明确时间优势时，跨链调用比例和前沿质量才同步提升。本文为共享制造平台中的多价值链资源协同提供了一种可计算、可解释且可复现实验的双目标调度框架。

**关键词：** 共享制造；分布式柔性作业车间；多服务价值链；供需匹配；跨链协同；估计分布算法；禁忌搜索；双目标优化

## 1 引言

共享制造通过平台化方式聚合分散的制造资源，使不同企业、车间和服务资源单元能够在统一调度机制下响应多源订单。与传统单车间或单企业调度相比，共享制造环境中的调度问题不仅要决定工序顺序、机器选择和完工时间，还要决定订单需求与制造服务能力之间的匹配关系。服务化制造平台中的资源通常不是孤立机器，而是具有服务类型、地理位置、业务归属和协同成本的制造服务资源单元。因此，调度模型必须同时刻画资源选择与车间内部排程，才能解释平台如何在成本与工期之间形成可执行的折中方案。

已有共享制造分布式柔性作业车间调度研究将制造资源抽象为服务资源单元（service resource unit, SRU），并把订单服务类型与 SRU 服务能力之间的供需匹配纳入调度可行性判断。这一建模方式能够表达“订单需要什么制造能力”和“哪些 SRU 可以提供该能力”的关系。然而，在多服务价值链共同接入共享制造平台的场景中，订单的业务归属与订单的制造服务类型并不是同一概念。价值链归属反映订单来自哪一条业务链、客户群或核心企业协同关系，服务类型则反映订单需要哪类加工能力。若仅以服务类型判断 SRU 是否可用，模型会忽略链内资源与跨链资源在协同成本、运输时间、资源偏好和管理边界上的差异。

这一差异在实际调度中会改变问题结构。对于同一订单，链内 SRU 可能具有较低协调成本，但因局部负载较高而导致较长完工时间；跨链 SRU 可能加工更快或负载更低，但需要支付额外运输和固定协同成本。平台的决策并不是简单地寻找“可加工”的 SRU，而是在链内稳定性和跨链协同收益之间进行权衡。换言之，多服务价值链共享制造调度需要同时回答三个问题：订单属于哪条价值链，订单需要哪类制造服务，以及在链内和跨链候选资源中应如何选择并排程。

本文围绕这一未被充分建模的能力缺口，提出 MVC-SM-DFJSP。该问题以静态订单池为研究对象，每个订单具有固定价值链归属和固定服务类型，每个 SRU 具有所属价值链和可服务类型。订单只能选择服务类型匹配的 SRU；在不允许跨链模式下，订单只能选择本价值链 SRU；在允许跨链模式下，订单可在同类型链内和跨链候选 SRU 中选择。完成 SRU 分配后，调度器还需要在 SRU 内部决定机器选择和工序排序。本文将总成本和最大完工时间作为正式优化目标，并将跨链比例、跨链流、价值链流入流出、SRU 负载标准差等变量作为管理诊断指标，从而避免把辅助解释指标与核心优化目标混淆。

为求解该问题，本文提出 MVC-EDA-TS。该算法不是对 EDA-TS 的直接套用，而是在调度表示、概率学习和局部搜索中注入价值链知识。算法使用 UA、OS、OP 和 MS 四层编码表达订单-SRU 分配、工序序列、SRU 内部工序队列和机器选择；在 UA 层构建价值链先验概率，使采样过程能够同时考虑链内低成本方案和跨链短工期方案；在禁忌搜索中设计链内替换、跨链替换、跨链回流、关键订单迁移、成本回流和机器/工序重排等邻域；并通过非支配解档案与自适应邻域选择维持 Pareto 前沿多样性。

本文的创新点与主要贡献如下。为避免把基础 EDA-TS 框架的通用组件表述为本文独有贡献，本文将创新限定在多服务价值链共享制造调度的建模、价值链感知搜索机制及其实验验证上。

1. **问题建模创新。** 提出 MVC-SM-DFJSP，显式区分订单价值链归属和制造服务类型需求，将传统“服务类型-SRU-机器”共享制造调度扩展为“价值链-服务类型-SRU-机器”的层级调度问题。该建模使链内稳定加工与跨链协同加工能够在同一可行域中比较，而不是把跨链资源简单视为普通备用资源。
2. **目标与诊断体系创新。** 构建总成本和最大完工时间双目标模型，将加工成本、运输成本和跨链固定协同成本纳入统一成本函数，并把跨链比例、跨链流、价值链流入流出和 SRU 负载分布作为诊断指标。这样既保持优化目标简洁，又能解释 Pareto 解背后的资源协同行为。
3. **价值链感知概率学习创新。** 在 EDA-TS 的 PMA/PMS/PMM 概率模型基础上，重点改造 PMA，使订单-SRU 分配概率同时受精英解频率和价值链先验约束。该先验综合加工成本、运输成本、跨链固定成本、预计完成时间和跨链时间收益，使采样过程能够在链内低成本方案与跨链短工期方案之间形成可学习的偏置。
4. **跨链协同局部搜索创新。** 设计链内 SRU 替换、跨链 SRU 替换、跨链回流、关键订单迁移和高成本跨链回流等问题特定邻域，并结合自适应邻域选择和非支配解档案，使局部搜索能够直接作用于价值链调用关系，而不仅是传统机器选择或工序排序调整。
5. **可复现实验与内部基线验证。** 基于 MK/FJSP benchmark 构造 MVC-MK01 至 MVC-MK15 扩展实例，并设置 NSGA-II、MOEA/D 和 Plain EDA-TS 基线。Plain EDA-TS 用于分离 EDA-TS 搜索框架本身与 MVC 价值链机制的贡献；小规模 exact validation 用于验证模型、目标函数与解码器的一致性；统计检验结果显示，MVC-EDA-TS 在 HV、IGD、最低总成本和最短 makespan 上整体优于三个基线。

本文其余部分组织如下。第 2 节综述相关研究。第 3 节定义 MVC-SM-DFJSP 并给出数学模型。第 4 节介绍 MVC-EDA-TS 算法。第 5 节说明实例构造、实验设置和评价指标。第 6 节报告实验结果。第 7 节讨论发现、边界和未来方向。第 8 节总结全文。

## 2 相关研究

### 2.1 柔性作业车间与分布式柔性作业车间调度

柔性作业车间调度问题要求同时决定每道工序的机器选择和机器上的加工顺序，是典型的 NP-hard 组合优化问题。分布式柔性作业车间调度进一步引入工厂或制造单元分配，使作业分配、机器选择和工序排序形成多层耦合。已有研究围绕遗传算法、禁忌搜索、人工蜂群、估计分布算法、变邻域搜索、模因算法和多目标进化算法提出了大量求解方法。这些工作证明了问题特定编码、可行性修复和局部搜索对复杂调度问题的重要性。

然而，传统 DFJSP 中的工厂或制造单元通常被视为生产组织单元，其可用性主要由加工能力和负载决定。共享制造平台下的 SRU 还带有服务属性、供需匹配关系和跨组织协同成本。本文在 DFJSP 的多层调度结构上进一步引入服务类型匹配和价值链归属，使制造单元选择不仅是产能分配问题，也是多价值链协同决策问题。

### 2.2 共享制造、云制造与供需匹配

共享制造和云制造研究强调通过平台连接制造服务供给方与需求方，实现资源发现、服务组合、供需匹配和协同加工。相关研究通常以成本、时间、服务质量、可靠性或能耗为优化指标，将制造任务与服务资源匹配为多目标、多约束组合优化问题。共享制造中的调度问题还需要考虑资源开放性、平台协调、运输时间和多主体协作。

已有 SM-DFJSP 研究把共享制造资源抽象为 SRU，并在分布式柔性作业车间调度中加入供需匹配约束，为本文提供了直接基础。Wei 等在 Computers & Industrial Engineering 发表的 SM-DFJSP 研究以共享制造资源组织结构为出发点，将订单和 SRU 均按供需类型划分，要求订单只能分配给同类型 SRU，并以总成本和最大完工时间为双目标；其总成本由加工成本和客户-SRU 运输成本构成，算法上采用 EDA-TS、多种群策略、非支配解记忆以及 UA/OS/OP/MS 四层编码，并在 G01-G03、SDMK01-15、SDMK16-25 和模具共享制造案例上验证。这一工作解决了“不同制造服务需求如何匹配异构 SRU 并完成 SRU 内部排程”的问题，但其供需类型同时承担了需求类别和资源类别的作用，没有进一步区分订单所属业务价值链与订单所需制造服务类型。

本文在该 SM-DFJSP 框架上做面向多服务价值链场景的扩展。核心差异不是改变 SRU 内部柔性作业车间排程的基本结构，而是把“服务类型匹配”从唯一的资源可用性判据扩展为“服务类型匹配 + 价值链归属 + 链内/跨链模式”的联合判据。由此，订单可在同服务类型的链内 SRU 和跨链 SRU 之间进行选择，跨链调用会触发固定协调成本和运输成本，并通过跨链比例、跨链流、价值链流入流出和 SRU 负载分布进行诊断。相应地，MVC-EDA-TS 保留 EDA-TS 的四层编码和概率学习思想，但把 PMA 层从供需类型一致性学习扩展为价值链感知的订单-SRU 分配学习，并增加链内替换、跨链替换、跨链回流、关键订单迁移和成本回流等直接作用于价值链调用关系的局部邻域。

| 对比维度 | 既有 SM-DFJSP 供需匹配模型 | 本文 MVC-SM-DFJSP |
| --- | --- | --- |
| 资源组织语义 | 订单和 SRU 按供需类型匹配 | 订单同时具有价值链归属和服务类型需求，SRU 同时具有价值链归属和可服务类型 |
| 候选 SRU | 同供需类型 SRU | 同服务类型的链内候选 SRU 与跨链候选 SRU |
| 成本结构 | 加工成本 + 客户-SRU 运输成本 | 加工成本 + 运输成本 + 跨链固定协调成本 |
| 协同行为解释 | 主要解释供需类型匹配与 SRU 内部排程 | 进一步解释跨链比例、价值链流入流出和 SRU 负载变化 |
| 搜索机制 | EDA-TS、多种群策略、非支配解记忆、通用邻域 | 价值链先验 PMA、链内/跨链 SRU 邻域、跨链回流和成本回流 |
| 实验数据 | G01-G03、SDMK01-25 和模具共享制造案例 | MVC-MK01-15、可穷举小规模 MVC 实例、integrated mechanism 和 mk14/mk15 机制案例 |

更具体地说，本文相对于该 SM-DFJSP 供需匹配模型的改进点包括四个方面。第一，在问题语义上，本文把供需类型拆分为订单价值链归属和制造服务类型需求，使模型能够描述“同一制造服务类型在不同价值链之间共享”的情形。第二，在约束结构上，本文把候选 SRU 分成链内候选和跨链候选，并通过 cross-off/cross-on 两种模式控制是否允许跨链调用，从而可以直接比较链内封闭调度和跨链开放调度。第三，在成本与诊断上，本文在加工成本和运输成本之外加入跨链固定协调成本，并记录跨链比例、价值链流入流出和 SRU 负载分布，使实验结果能够解释跨链行为，而不仅是报告目标函数数值。第四，在实验设计上，本文除基于 MK/FJSP 的 MVC 扩展实例外，还构造 integrated mechanism 和 mk14/mk15 聚焦机制案例，用于区分跨链时间优势和链内拥堵两种不同收益来源。

### 2.3 跨资源单元协同与运输扩展

DFJSP with transfers、带运输的分布式调度、维护约束调度和动态调度研究表明，跨资源单元协同会显著扩大解空间，并使运输时间、运输成本和局部搜索结构成为影响性能的关键因素。与工序级跨工厂转运不同，本文当前采用订单级 SRU 分配：一个订单被分配给一个满足服务类型要求的 SRU，并在该 SRU 内部完成机器选择和工序排序。跨链并不表示工序在多个 SRU 间频繁转移，而表示订单从所属价值链调用其他价值链的开放 SRU。

这一设定有两个好处。第一，它保留了共享制造中“订单-服务资源单元”匹配的管理语义，易于解释跨链协同成本。第二，它将本文的核心问题聚焦在价值链归属和 SRU 选择上，避免在首个模型中同时引入工序级转运带来的额外复杂性。工序级跨链转运、动态订单到达和设备扰动可作为后续扩展。

### 2.4 多目标启发式与学习增强调度算法

共享制造调度通常存在天然的多目标冲突。降低成本往往倾向于选择链内或低成本资源，缩短工期则可能需要调用更快但成本更高的资源。NSGA-II 和 MOEA/D 等经典多目标算法可提供通用 Pareto 搜索框架，但在多层编码、供需匹配和跨链成本结构下，通用交叉变异算子可能难以充分利用问题知识。

估计分布算法通过概率模型学习优质解结构，适合处理多层离散决策。禁忌搜索和变邻域搜索能够围绕当前优质解进行有方向的局部改进。近年来，问题知识、学习驱动算子、自适应邻域和强化学习也被用于复杂 DFJSP。本文采用更可解释的知识嵌入路线，将价值链归属、服务类型匹配、跨链固定成本和跨链时间收益写入概率先验和邻域结构，而不是使用端到端黑箱策略。

## 3 问题定义与数学模型

### 3.1 调度场景

考虑一个第三方共享制造平台。平台接入若干服务价值链 \(V\)、订单集合 \(J\)、服务类型集合 \(T\)、SRU 集合 \(U\) 以及 SRU 内部机器集合 \(M_u\)。每个订单 \(j\) 具有价值链归属 \(vc_j\) 和服务类型需求 \(type_j\)。每个 SRU \(u\) 具有价值链归属 \(vc_u\) 和可服务类型集合 \(types_u\)。若 \(type_j\in types_u\)，则 SRU \(u\) 在能力上可服务订单 \(j\)；若进一步满足 \(vc_j=vc_u\)，则该候选为链内候选；否则为跨链候选。

平台需要在给定订单池下生成调度方案。该方案包括：订单到 SRU 的分配，SRU 内部每道工序的机器选择，以及每台机器上的工序排序。调度方案必须满足服务类型匹配、跨链模式约束、订单工序先后约束和机器不重叠约束。本文研究确定性静态调度，不考虑动态到达、机器故障和随机加工时间。

### 3.2 集合、参数与变量

主要集合如下。

| 符号 | 含义 |
| --- | --- |
| \(J\) | 订单集合 |
| \(V\) | 服务价值链集合 |
| \(T\) | 服务类型集合 |
| \(U\) | SRU 集合 |
| \(M_u\) | SRU \(u\) 内部机器集合 |
| \(O_j\) | 订单 \(j\) 的工序集合 |
| \(A_j\) | 订单 \(j\) 的候选 SRU 集合 |
| \(A_j^{in}\) | 订单 \(j\) 的链内候选 SRU 集合 |
| \(A_j^{cross}\) | 订单 \(j\) 的跨链候选 SRU 集合 |

主要参数如下。

| 符号 | 含义 |
| --- | --- |
| \(vc_j\) | 订单 \(j\) 所属价值链 |
| \(type_j\) | 订单 \(j\) 的服务类型需求 |
| \(vc_u\) | SRU \(u\) 所属价值链 |
| \(types_u\) | SRU \(u\) 可服务类型集合 |
| \(p_{j,o,u,m}\) | 工序 \((j,o)\) 在 SRU \(u\) 的机器 \(m\) 上的加工时间 |
| \(c_{j,o,u,m}\) | 工序 \((j,o)\) 在 SRU \(u\) 的机器 \(m\) 上的单位加工成本 |
| \(tt_{j,u}\) | 订单 \(j\) 选择 SRU \(u\) 后的运输时间 |
| \(tc_{j,u}\) | 订单 \(j\) 选择 SRU \(u\) 后的运输成本 |
| \(fc_{j,u}\) | 订单 \(j\) 跨链选择 SRU \(u\) 的固定协调成本 |

主要决策变量如下。

| 符号 | 含义 |
| --- | --- |
| \(x_{j,u}\) | 若订单 \(j\) 分配给 SRU \(u\)，则为 1，否则为 0 |
| \(y_{j,o,u,m}\) | 若工序 \((j,o)\) 在 SRU \(u\) 的机器 \(m\) 上加工，则为 1，否则为 0 |
| \(s_{j,o}\) | 工序 \((j,o)\) 的开始时间 |
| \(e_{j,o}\) | 工序 \((j,o)\) 的完成时间 |
| \(q_{j,u}\) | 若订单 \(j\) 跨链分配给 SRU \(u\)，则为 1，否则为 0 |

### 3.3 候选 SRU 与跨链模式

订单 \(j\) 的候选 SRU 集合定义为：

\[
A_j = A_j^{in} \cup A_j^{cross}
\]

其中：

\[
A_j^{in} = \{u\in U \mid type_j\in types_u,\ vc_j=vc_u\}
\]

\[
A_j^{cross} = \{u\in U \mid type_j\in types_u,\ vc_j\ne vc_u\}
\]

当实验模式不允许跨链时，订单只能选择 \(A_j^{in}\)。当实验模式允许跨链时，订单可以在 \(A_j^{in}\cup A_j^{cross}\) 中选择。跨链变量定义为：

\[
q_{j,u}=1,\quad \text{if }x_{j,u}=1\text{ and }vc_j\ne vc_u
\]

否则 \(q_{j,u}=0\)。

### 3.4 目标函数

本文采用双目标优化：

\[
\min F_1 = total\_cost
\]

\[
\min F_2 = makespan
\]

总成本由加工成本、运输成本和跨链固定协调成本构成：

\[
F_1 = PC + TC + CFC
\]

\[
PC=\sum_{j\in J}\sum_{o\in O_j}\sum_{u\in U}\sum_{m\in M_u}
p_{j,o,u,m}c_{j,o,u,m}y_{j,o,u,m}
\]

\[
TC=\sum_{j\in J}\sum_{u\in U}tc_{j,u}x_{j,u}
\]

\[
CFC=\sum_{j\in J}\sum_{u\in U}fc_{j,u}q_{j,u}
\]

当前正式口径中，跨链变动成本率字段仅作为历史兼容字段保留，不参与目标函数。

最大完工时间定义为：

\[
F_2=\max_{j\in J}(C_j+tt_{j,u})
\]

其中 \(C_j\) 为订单 \(j\) 最后一道工序的完成时间，\(u\) 为订单 \(j\) 被分配的 SRU。

### 3.5 约束条件

每个订单只能分配给一个 SRU：

\[
\sum_{u\in U}x_{j,u}=1,\quad \forall j\in J
\]

订单只能选择服务类型匹配的 SRU：

\[
x_{j,u}=0,\quad type_j\notin types_u
\]

当不允许跨链时，订单只能选择本价值链 SRU：

\[
x_{j,u}=0,\quad vc_j\ne vc_u,\quad cross\_chain\_allowed=0
\]

工序只能在订单已分配的 SRU 内加工：

\[
\sum_{m\in M_u}y_{j,o,u,m}=x_{j,u},\quad \forall j,o,u
\]

同一订单内工序满足先后约束：

\[
s_{j,o+1}\ge e_{j,o},\quad \forall j,o
\]

同一机器同一时刻只能加工一道工序，且加工不可中断。工程实现中，该约束由解码过程维护的 `job_ready` 和 `machine_ready` 隐式保证。

### 3.6 诊断指标

为解释跨链协同机制，本文记录但不作为正式优化目标的诊断指标包括：

| 指标 | 含义 |
| --- | --- |
| \(cross\_chain\_ratio\) | 跨链订单数占订单总数的比例 |
| \(cross\_chain\_flow\) | 不同价值链之间的跨链调用流 |
| \(value\_chain\_inflow\) | 价值链接收外链订单数量 |
| \(value\_chain\_outflow\) | 价值链向外链转出的订单数量 |
| \(sru\_load\_std\) | SRU 负载标准差 |
| \(max\_sru\_load\) | 最大 SRU 负载 |

这些指标用于解释 Pareto 前沿背后的资源流动和负载变化，而不与 \(F_1\) 和 \(F_2\) 混合作为第三目标。

## 4 MVC-EDA-TS 算法

### 4.1 总体思路

MVC-EDA-TS 由四个核心模块组成：多层编码与可行性修复、价值链感知概率模型、跨链协同禁忌搜索、非支配解档案与自适应邻域选择。算法首先基于价值链、服务类型和候选 SRU 生成初始种群；随后评价个体并建立非支配档案；每轮迭代中，算法从精英解和档案中学习概率模型，采样新个体，执行可行性修复和局部搜索，最后更新档案和种群。

算法流程如下。

```text
Input: MVC-SM-DFJSP instance, algorithm parameters, cross_chain_allowed
Output: non-dominated solution archive

1. Build intra-chain and cross-chain candidate SRU sets.
2. Build value-chain-aware prior probabilities for UA.
3. Initialize population with mixed MVC-aware strategies.
4. Evaluate population and initialize non-dominated archive.
5. while the stopping criterion is not met:
6.     Select elites by Pareto rank and crowding distance.
7.     Build the learning set from elites and archive.
8.     Update PMA, PMS and PMM.
9.     Sample new individuals from the probability model.
10.    Repair infeasible assignments and decode schedules.
11.    Apply tabu search with value-chain-aware neighborhoods.
12.    Update adaptive neighborhood probabilities.
13.    Update the non-dominated archive.
14.    Select the next population.
15. Return the archive.
```

### 4.2 四层编码

个体使用 UA、OS、OP 和 MS 四层编码。

UA（unit assignment）表示订单到 SRU 的分配关系。UA 是本文价值链协同的关键层，因为它直接决定订单是链内加工还是跨链加工。

OS（operation sequence）表示订单工序排序序列。项目实现中按服务类型维护 OS，每个订单在 OS 中出现的次数等于其工序数。

OP（operation list per SRU）由 UA 和 OS 推导，表示每个 SRU 内部需要加工的工序队列。

MS（machine selection）表示每个 SRU 内部工序对应的机器选择。

该编码使算法能够同时表达订单级跨链资源选择和 SRU 内部柔性作业车间排程。

### 4.3 解码与可行性修复

解码前，算法检查 UA 是否满足服务类型匹配和跨链模式约束。若订单被分配到不可行 SRU，则修复算子在候选 SRU 集合中重新选择可行资源。随后，算法由 UA 和 OS 生成 OP，并按 MS 依次安排工序。每道工序的开始时间由订单就绪时间和机器就绪时间共同决定：

\[
start_{j,o}=\max(job\_ready_j,machine\_ready_{u,m})
\]

完成时间为：

\[
end_{j,o}=start_{j,o}+p_{j,o,u,m}
\]

所有工序完成后，算法计算加工成本、运输成本、跨链固定协调成本、最大完工时间、SRU 负载和跨链诊断指标。

### 4.4 价值链感知初始化

初始种群需要覆盖低成本链内方案、短工期跨链方案和随机探索方案。本文使用混合初始化策略，包括随机初始化、链内优先、成本优先、时间优先和跨链收益优先。链内优先策略倾向于生成低协调成本解；时间优先和跨链收益优先策略用于探索跨链资源可能带来的 makespan 改进；随机策略维持种群多样性。

这一设计的目的不是强制算法跨链，而是让初始种群同时看到保守链内方案和进取跨链方案，从而为后续概率学习提供更完整的结构样本。

### 4.5 价值链先验概率模型

MVC-EDA-TS 使用 PMA、PMS 和 PMM 分别学习 UA、OS 和 MS 的优质结构。本文的核心改进集中在 UA 概率模型。对于每个订单 \(j\) 和候选 SRU \(u\)，构建价值链感知评分：

三类概率模型的作用和创新边界如下。PMA（probability matrix of assignment）对应 UA 层，学习订单选择各可行 SRU 的概率，直接决定链内或跨链资源调用；PMS（probability matrix of sequence）对应 OS 层，学习同一服务类型内订单工序在排序序列中的位置偏好；PMM（probability matrix of machine）对应 MS 层，学习特定订单工序在给定 SRU 内选择各可加工机器的概率。PMS 和 PMM 主要继承 EDA-TS 对工序排序与机器选择的概率学习机制，并适配到 MVC-SM-DFJSP 的服务类型和 SRU 编码；本文的关键创新在于 PMA 的价值链感知改造，因为 UA 层同时承载服务类型匹配、价值链归属和链内/跨链资源选择。

\[
score(j,u)=
w_1\hat{PC}_{j,u}
+w_2\hat{TC}_{j,u}
+w_3\hat{CFC}_{j,u}
+w_4\hat{CT}_{j,u}
-w_5\hat{Gain}_{j,u}
\]

其中 \(\hat{PC}_{j,u}\)、\(\hat{TC}_{j,u}\)、\(\hat{CFC}_{j,u}\) 和 \(\hat{CT}_{j,u}\) 分别表示归一化后的加工成本、运输成本、跨链固定成本和预计完成时间，\(\hat{Gain}_{j,u}\) 表示相对于最佳链内候选的跨链时间收益。评分通过 softmax 转换为先验概率：

\[
P_{prior}(j,u)=
\frac{\exp(-score(j,u)/\tau)}
{\sum_{v\in A_j}\exp(-score(j,v)/\tau)}
\]

每轮迭代中，根据精英解统计得到 \(P_{elite}(j,u)\)，并与先验概率融合：

\[
P_{target}(j,u)=(1-\lambda)P_{elite}(j,u)+\lambda P_{prior}(j,u)
\]

最终按学习率更新 PMA：

\[
PMA_{new}=(1-\alpha)PMA_{old}+\alpha P_{target}
\]

通过这种方式，算法能够在数据驱动的精英频率和问题知识驱动的价值链先验之间保持平衡。

### 4.6 跨链协同禁忌搜索

局部搜索阶段使用多类邻域：

| 邻域 | 作用 |
| --- | --- |
| 链内 SRU 替换 | 在同价值链、同服务类型 SRU 中移动订单 |
| 跨链 SRU 替换 | 将订单迁移到其他价值链的同服务类型 SRU |
| 跨链回流 | 将已跨链订单迁回本价值链 SRU |
| 关键订单迁移 | 将影响 makespan 的关键订单迁移至更短预计完成时间的候选 SRU |
| 高成本跨链回流 | 将跨链成本较高的订单迁回链内或低成本候选 |
| 机器与工序重排 | 保持传统 FJSP 内部排程优化能力 |

禁忌表用于避免短期循环。若候选解能够进入全局非支配解档案，则允许破禁。每类邻域的贡献通过接受次数、进入档案次数和目标改进记录，并用于更新邻域选择概率。

### 4.7 非支配解档案与自适应邻域

非支配解档案保存搜索过程中发现的 Pareto 优质解，并按目标值去重。档案既为概率模型提供学习样本，也为禁忌搜索提供局部搜索种子。当档案超过容量时，算法使用拥挤距离保留分布较分散的解。

自适应邻域选择根据邻域贡献更新调用概率。若某类邻域更频繁地产生可接受解或插入非支配档案，其后续被选择的概率会提高。该机制使算法能够根据实例特点在成本压缩、工期压缩和跨链回流之间动态分配搜索资源。

### 4.8 与既有 EDA-TS 的算法差异

MVC-EDA-TS 继承了既有 SM-DFJSP EDA-TS 的基本求解思想，即使用四层编码描述 SRU 分配、工序排序、SRU 内部工序队列和机器选择，并通过 PMA、PMS 和 PMM 学习优质解结构，再由禁忌搜索强化局部改进。但二者的搜索对象不同：原 EDA-TS 面向供需类型一致的 SRU 分配，MVC-EDA-TS 面向价值链归属、服务类型匹配和链内/跨链资源调用共同决定的分配决策。下表总结了两类算法的主要差异。

| 对比维度 | 既有 SM-DFJSP EDA-TS | 本文 MVC-EDA-TS | 改进含义 |
| --- | --- | --- | --- |
| 问题语义 | 订单和 SRU 按供需类型匹配 | 订单同时具有价值链归属和服务类型需求，SRU 同时具有价值链归属和可服务类型 | 将“制造能力是否匹配”和“是否跨越价值链边界调用资源”分开建模 |
| UA 层含义 | 表示订单分配到哪个同供需类型 SRU | 表示订单选择链内 SRU 还是跨链同服务类型 SRU | UA 层从普通资源分配扩展为价值链协同决策层 |
| 候选资源集合 | 由供需类型一致性确定 | 先由服务类型匹配确定，再划分链内候选和跨链候选 | 支持 cross-off/cross-on 两种模式下的可行域比较 |
| 初始化策略 | 随机生成、概率模型采样和 MD、MC、MCT 等调度规则 | 随机、链内优先、成本优先、时间优先和跨链收益优先 | 初始种群同时覆盖链内低成本方案和跨链短工期方案 |
| PMA 概率学习 | 依据精英解中订单-SRU 分配频率更新，核心约束是供需类型一致 | 精英解频率与价值链先验融合，先验综合加工成本、运输成本、跨链固定成本、预计完成时间和跨链时间收益 | 采样概率不仅复制历史优质结构，还嵌入链内/跨链成本-时间权衡知识 |
| PMS/PMM 学习 | 学习工序排序和机器选择结构 | 基本继承 PMS/PMM，并适配 MVC 的服务类型、SRU 和机器编码 | 保留既有 EDA-TS 在车间内部排序与机器选择上的有效机制 |
| 禁忌搜索邻域 | 主要围绕一般 SRU 分配、工序排序和机器选择改进 | 增加链内 SRU 替换、跨链 SRU 替换、跨链回流、关键订单迁移和高成本跨链回流 | 局部搜索可直接改变跨链比例、价值链流向和瓶颈订单分配 |
| 非支配解记忆 | 用于保存 Pareto 优质解并增强搜索稳定性 | 非支配档案同时参与概率模型学习和局部搜索种子选择 | 档案不仅保存结果，也反向引导后续采样和局部搜索 |
| 搜索控制 | 主要依赖固定算法参数和禁忌机制 | 记录邻域接受次数、进入档案次数和目标改进，并进行自适应邻域选择 | 根据实例特点在链内成本压缩、跨链工期压缩和跨链回流之间分配搜索强度 |
| 结果解释 | 主要解释供需匹配后的成本和工期折中 | 同时输出跨链比例、价值链流入流出和 SRU 负载变化 | 算法结果可用于分析跨链机制是否被激活及其收益来源 |

从该对比可以看出，MVC-EDA-TS 并不是对既有 EDA-TS 的完全重写，而是在保留四层编码、概率学习和禁忌搜索框架的基础上，对承载资源分配的 UA 层进行了价值链语义扩展。既有 EDA-TS 的 PMA 主要回答“同供需类型下选择哪个 SRU”，而本文 PMA 进一步回答“在服务类型匹配的前提下，订单应选择链内 SRU 还是跨链 SRU”。因此，本文的算法改进集中在价值链先验、跨链候选集和跨链邻域上，而 PMS、PMM 以及 SRU 内部工序排序和机器选择机制主要继承既有 EDA-TS 的思想。

这种改进的收益具有条件性。当跨链资源没有加工时间优势且只增加协调成本时，cross-on 只扩大可行域和搜索空间，未必带来稳定收益；当存在跨链时间优势或链内 SRU 拥堵时，价值链先验和跨链邻域更容易被激活，使算法能够通过跨链资源调用改善 makespan、Pareto 前沿质量或 SRU 负载均衡。因此，本文将 MVC-EDA-TS 表述为面向多服务价值链场景的 EDA-TS 扩展，而不是对既有 EDA-TS 的替代。

## 5 实验设计

### 5.1 数据构造

本文基于 MK/FJSP benchmark 构造 MVC-MK01 至 MVC-MK15 扩展实例。当前正式数据集为 `mvc_mk01_15_2vc4sru_equalproc_vcpenalty`。构造规则如下。

1. 价值链：设置 VC1 和 VC2，按 job id 轮转分配订单价值链归属。
2. 服务类型：设置 T1 和 T2，按工序数划分订单服务类型。
3. SRU：设置 4 个 SRU，即 U1=VC1-T1、U2=VC1-T2、U3=VC2-T1、U4=VC2-T2。
4. 候选资源：每个订单恰好具有一个服务类型匹配的链内 SRU 和一个服务类型匹配的跨链 SRU。
5. 加工时间：候选 SRU 上的加工时间与原 MK 加工时间保持一致。
6. 加工成本：单位加工成本依赖原始机器，在候选 SRU 间保持一致。
7. 运输成本：链内运输时间为 \(2+job\_id\bmod2\)，单位运输成本为 1.8；跨链运输时间为 \(7+job\_id\bmod3\)，单位运输成本为 4.8。
8. 跨链固定成本：跨链固定协调成本为 200.0；`cross_chain_cost_rate` 固定为 0。

正式总成本口径为：

```text
total_cost = processing_cost + transport_cost + cross_fixed_cost
```

### 5.2 对比算法与实验参数

主实验比较 3 类算法：NSGA-II、MOEA/D 和 MVC-EDA-TS。每类算法均在 cross-off 和 cross-on 两种模式下运行。cross-off 表示不允许跨链，cross-on 表示允许订单选择服务类型匹配的跨链 SRU。为分离 EDA-TS 搜索框架本身与 MVC 价值链机制的贡献，本文另设 Plain EDA-TS 基线，即保留 EDA-TS 主体搜索框架但去除 MVC 价值链感知设计的简化版本。Plain EDA-TS 在 cross-off 模式下运行，并与 NSGA-II-off、MOEA/D-off 和 MVC-EDA-TS-off 进行统一统计比较。

主实验参数如下。

| 参数 | 设置 |
| --- | --- |
| 实例 | MVC-MK01 至 MVC-MK15 |
| 算法 | NSGA-II, MOEA/D, MVC-EDA-TS；Plain EDA-TS 作为 cross-off 内部基线 |
| 跨链模式 | off, on |
| 随机种子 | 20260428 至 20260432 |
| 种群规模 | 80 |
| 最大迭代 | 150 |
| 时间上限 | 12000 s |
| 目标维度 | 2 |

主实验共包含 \(15\times3\times2\times5=450\) 次运行。Plain EDA-TS 基线另包含 \(15\times1\times1\times5=75\) 次运行。运行记录显示主比较实验、Plain EDA-TS 基线和轻量消融实验均已完成；可用敏感性汇总目前覆盖 mk05 三个随机种子。

### 5.3 评价指标

本文使用以下指标评价算法性能。

| 指标 | 方向 | 含义 |
| --- | --- | --- |
| HV | 越大越好 | 前沿收敛性和覆盖范围 |
| IGD | 越小越好 | 生成前沿到参考前沿的平均距离 |
| GD | 越小越好 | 生成前沿到参考前沿的距离 |
| Spacing | 越小越好 | 前沿分布均匀性 |
| Front size | 越大通常越好 | 非支配解数量 |
| Min total cost | 越小越好 | 当前前沿最低总成本 |
| Min makespan | 越小越好 | 当前前沿最短最大完工时间 |
| Runtime | 越小越好 | 单次运行时间 |
| Cross-chain ratio | 解释指标 | 非支配解中的平均跨链比例 |

### 5.4 消融与敏感性实验

轻量消融实验选择 mk05、mk10 和 mk15，使用 cross-on 模式、3 个随机种子和 6 个变体：

| 变体 | 含义 |
| --- | --- |
| Full | 完整 MVC-EDA-TS |
| No-VC-init | 去除价值链感知初始化 |
| No-prior | 去除价值链先验概率 |
| No-cross-neighbors | 去除跨链相关邻域 |
| No-adaptive-neighborhood | 去除自适应邻域选择 |
| No-archive | 去除非支配解档案 |

敏感性实验计划改变跨链固定成本、运输成本比例和跨链时间比例，用于分析跨链协同是否受成本与时间参数驱动。当前结果文件夹中，可用 `sensitivity_summary.csv` 覆盖 mk05 的三个随机种子；mk10 仅保留 raw 运行文件，mk15 未形成可用汇总。因此，敏感性实验在本文中仅作为 mk05 上的机制趋势证据，而非全实例统计结论。

### 5.5 小规模精确验证

为验证数学模型、目标函数和解码过程的一致性，本文构造 3 个可穷举的小规模 MVC-SM-DFJSP 实例。小规模实例覆盖 2 条价值链、2 类服务类型、4 个 SRU、每个 SRU 1 到 2 台机器，以及 3 到 5 个订单。每个订单保留链内候选 SRU 和同服务类型跨链候选 SRU，因此可以分别检查 cross-off 模式下的链内约束和 cross-on 模式下的同类型跨链选择。

验证脚本 `scripts/run_mvc_small_exact_validation.py` 对每个实例分别在 cross-off 和 cross-on 模式下枚举 UA、OS 和 MS 组合，并调用与主实验相同的 `evaluate_mvc_individual()` 计算总成本和最大完工时间。枚举结果用于提取 exact nondominated front；随后使用小预算 MVC-EDA-TS 与 exact front 比较。该验证输出 exact coverage、false nondominated count、infeasible count、HV gap 和 IGD，并生成成本审计表与调度区间审计表。成本审计逐项记录加工成本、运输成本、跨链固定协调成本和订单完成时间；调度审计检查机器不重叠和工序 precedence 约束。

### 5.6 中等规模 integrated-mechanism equal-processing 对比实验

为进一步检验 MVC-EDA-TS 的价值链感知搜索机制是否能在中等规模机制实例上稳定发挥作用，本文补充 `mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2` 实验。该实验不替代 5.2 节的正式主实验，而是作为机制型数据集上的补充证据：一方面考察 MVC-EDA-TS 在 cross-off 条件下相对 NSGA-II、MOEA/D 和 Plain EDA-TS 的算法优势，另一方面考察在加工时间保持等价时，开启跨链候选是否仍能通过负载再分配改善 Pareto 前沿和工期端表现。

该实验使用数据集 `data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc`，包含由 MK01 至 MK15 扩展得到的 15 个 integrated-mechanism equal-processing 实例。每个实例采用 2 条价值链、2 类服务类型和 4 个 SRU；验证结果显示，所有实例均满足 `total_cost = processing_cost + transport_cost + cross_fixed_cost` 与 `makespan = max(C_j + transport_time)` 的目标定义，跨链候选检查、固定跨链成本检查和 `cross_chain_cost_rate=0` 检查均通过。该数据集因此用于隔离“候选资源扩展和负载再分配”本身的贡献，而不是把收益归因于跨链加工时间优势。

实验分为两部分。实验 1 在 cross-off 模式下比较 NSGA-II、MOEA/D、Plain EDA-TS 和 MVC-EDA-TS，用于检验 MVC-EDA-TS 在不允许跨链时相对内部与外部基线的搜索性能。实验 2 仅运行 MVC-EDA-TS 的 cross-off 与 cross-on，用于检验开启跨链机制后的边际贡献。两部分统一使用 15 个实例、随机种子 20260428 和 20260429、种群规模 50、最大迭代 50、单次时间上限 600 s、目标维度 2。实验 1 共 \(15\times4\times1\times2=120\) 次运行；实验 2 共 \(15\times1\times2\times2=60\) 次运行；合并后用于统一指标、Pareto 前沿和统计检验分析。

### 5.7 mk14/mk15 聚焦机制案例实验

为进一步区分“跨链加工时间优势”和“链内负载拥堵”两种机制对跨链调度的不同影响，本文补充 `mechanism_cases_mk14_mk15_only` 聚焦机制案例实验。该实验使用 `data/mvc_mk01_15_2vc4sru_mechanism_vc_load` 数据集中的 mk14 和 mk15 两个较大规模实例，并分别构造 `cross_time_advantage` 与 `intra_congested` 两类场景。

两类场景共享 2 条价值链、2 类服务类型和 4 个 SRU 的结构，即 U1=VC1-T1、U2=VC1-T2、U3=VC2-T1、U4=VC2-T2；每个订单保留 1 个同类型链内 SRU 和 1 个同类型跨链 SRU。`cross_time_advantage` 场景保留原始较均衡的价值链分配，但将跨链加工时间设置为原始加工时间的 0.75 倍，同时设置跨链固定协调成本为 120.0、跨链运输时间为 \(5+job\_id\bmod2\)、跨链单位运输成本为 4.0。该场景检验算法是否会用更高协同成本换取更短工期。`intra_congested` 场景则按工作负载将每类服务中高负载订单集中分配给 VC1；对 mk14 和 mk15，前 80% 高负载订单进入 VC1，使 U1 和 U2 成为拥堵链内 SRU，而 U3 和 U4 成为同类型跨链缓解资源。该场景保持链内和跨链加工时间相同，设置跨链固定协调成本为 80.0、跨链运输时间为 \(4+job\_id\bmod2\)、跨链单位运输成本为 3.2。

实验仅运行 MVC-EDA-TS，比较 cross-off 与 cross-on。参数与正式主实验一致：随机种子 20260428 至 20260432、种群规模 80、最大迭代 150、单次时间上限 12000 s、目标维度 2。总运行数为 \(2\text{ instances}\times2\text{ scenarios}\times2\text{ cross modes}\times5\text{ seeds}=40\)。所有运行均以达到最大迭代数结束。该实验不是算法间主比较，而是用于解释跨链收益来自哪一种机制，以及两种机制对成本、工期、前沿质量和 SRU 负载均衡的影响是否相同。

## 6 实验结果

### 6.1 小规模精确验证支持模型与解码器一致性

小规模 exact validation 覆盖 3 个实例与 2 种跨链模式，共 6 个 instance/mode 组合。枚举规模从 `mvc_small_01` 的 3 个 cross-off 可行组合到 `mvc_small_02` 的 147,456 个 cross-on 可行组合不等。所有枚举解均通过可行性检查，`exact_infeasible_count=0`。

**表 1 小规模 exact validation 结果**

| Instance | Cross | Exact evaluations | Exact front | Algorithm front | Coverage | False ND | Infeasible | HV gap | IGD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mvc_small_01 | off | 3 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_01 | on | 24 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_02 | off | 9,216 | 2 | 2 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_02 | on | 147,456 | 2 | 2 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_03 | off | 192 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_03 | on | 6,144 | 3 | 3 | 1.0 | 0 | 0 | 0 | 0 |

MVC-EDA-TS 在 6 个组合中均恢复 exact nondominated front，`exact_coverage=1.0`，且 `false_nd_count=0`、`infeasible_count=0`、`exact_hv_gap=0`、`exact_igd=0`。调度审计表显示，审计解均满足机器不重叠和工序 precedence 约束；成本审计表进一步确认 `total_cost = processing_cost + transport_cost + cross_fixed_cost`，且 `makespan = max(C_j + transport_time)`。因此，小规模验证为本文的模型定义、成本口径、跨链约束处理和解码器可行性提供了直接证据。

### 6.2 主对比实验表明 MVC-EDA-TS 显著优于三个 cross-off 基线

表 2 给出 15 个实例、5 个随机种子下的 cross-off 统一对比结果。该表使用合并 Plain EDA-TS 后重新计算的统一指标，因此可直接比较 MVC-EDA-TS、Plain EDA-TS、NSGA-II 和 MOEA/D 在相同候选资源约束下的 Pareto 前沿质量。

**表 2 cross-off 主对比平均结果**

| 算法 | HV ↑ | IGD ↓ | Min total cost ↓ | Min makespan ↓ |
| --- | ---: | ---: | ---: | ---: |
| MVC-EDA-TS | \(2.348\times10^7\) | \(1.429\times10^4\) | \(1.538\times10^4\) | 158.5 |
| NSGA-II | \(2.190\times10^7\) | \(1.604\times10^4\) | \(1.713\times10^4\) | 179.0 |
| Plain EDA-TS | \(2.160\times10^7\) | \(1.525\times10^4\) | \(1.635\times10^4\) | 204.5 |
| MOEA/D | \(2.153\times10^7\) | \(1.594\times10^4\) | \(1.703\times10^4\) | 193.0 |

MVC-EDA-TS 在四项指标上均取得最佳平均值。相对于 NSGA-II，MVC-EDA-TS 的 HV 平均提高 12.21%，IGD 平均降低 25.05%，最低总成本平均降低 12.67%，最短 makespan 平均降低 13.83%。相对于 MOEA/D，对应改进分别为 15.77%、24.36%、12.03% 和 19.66%。相对于 Plain EDA-TS，MVC-EDA-TS 的 HV 平均提高 16.67%，IGD 平均降低 16.53%，最低总成本平均降低 6.68%，最短 makespan 平均降低 21.87%。这些结果说明，MVC-EDA-TS 的提升不仅来自 EDA-TS 搜索框架本身，还来自价值链感知初始化、先验概率和问题特定局部搜索等 MVC 设计。

### 6.3 Plain EDA-TS 是有效但不充分的内部基线

Plain EDA-TS 的作用是检验 EDA-TS 搜索框架本身是否足以解释性能提升。结果显示，Plain EDA-TS 并不是弱基线。与 NSGA-II 和 MOEA/D 相比，Plain EDA-TS 在 IGD 和最低总成本上显著更好；例如其平均 IGD 为 \(1.525\times10^4\)，低于 NSGA-II 的 \(1.604\times10^4\) 和 MOEA/D 的 \(1.594\times10^4\)，平均最低总成本也从 NSGA-II 的 \(1.713\times10^4\) 和 MOEA/D 的 \(1.703\times10^4\) 降至 \(1.635\times10^4\)。

然而，Plain EDA-TS 的不足同样明确。它在 HV 上与 NSGA-II 和 MOEA/D 没有显著差异，并且最短 makespan 显著差于两个通用基线。实例级排名进一步显示，Plain EDA-TS 在 IGD 和最低总成本上 15 个实例均排第 2，但在最短 makespan 上有 10 个实例排第 4。这表明 Plain EDA-TS 更倾向于压缩成本和收敛距离，却未能同时维持足够好的工期端搜索能力。MVC-EDA-TS 正是在这一点上补足了内部基线的短板：它在保留 EDA-TS 成本优势的同时，把最短 makespan 从 Plain EDA-TS 的 204.5 降至 158.5。

### 6.4 实例级胜负和统计检验支持主结论

按每个实例上 5 个随机种子的平均指标统计，MVC-EDA-TS 在 15 个实例中获得 14 个 HV 最优、15 个 IGD 最优、15 个最低总成本最优和 12 个最短 makespan 最优。NSGA-II 仅在 1 个实例上获得 HV 最优，并在 3 个实例上获得最短 makespan 最优；MOEA/D 和 Plain EDA-TS 在四项指标上均未获得实例级最优。

Wilcoxon signed-rank tests 给出了相同判断。MVC-EDA-TS-off 相对 NSGA-II-off、MOEA/D-off 和 Plain EDA-TS-off，在 HV、IGD、最低总成本和最短 makespan 上均显著更优；调整后 \(p\) 值均不高于 0.0369，其中大多数比较为 0.0073。Friedman tests 也显示四项指标的算法差异均显著，并将 MVC-EDA-TS 排为第一：HV 平均秩为 1.067，IGD、最低总成本均为 1.000，最短 makespan 为 1.200。

### 6.5 跨链机制表现为有条件收益

MVC-EDA-TS 的 cross-on 与 cross-off 比较显示，开启跨链后的平均 HV 从 \(2.348\times10^7\) 小幅提高至 \(2.353\times10^7\)，平均最短 makespan 从 158.5 降至 157.2，但最低总成本保持不变，IGD 反而从 14292.07 小幅增至 14292.16。Wilcoxon tests 显示，cross-on 对 HV、最低总成本和最短 makespan 的改进均不显著；IGD 的差异达到显著，但方向上是 cross-off 更好。实例级比较也显示 cross-on 的收益不稳定：HV 上 cross-on 赢 6 个实例、输 9 个实例；IGD 上仅赢 3 个实例；最短 makespan 上赢 5 个、平 3 个、输 7 个。

这一结果限定了跨链机制的解释边界。在当前 `equalproc_vcpenalty` 数据集中，跨链候选与链内候选在加工时间上保持一致，而跨链会带来额外运输和固定协调成本。因此，cross-on 并不是普遍提升算法性能的开关，而是为特定负载结构和特定时间优势场景提供额外可行协同空间。运行时间也反映了这一代价：MVC-EDA-TS-off 的平均运行时间为 310.6 s，而 MVC-EDA-TS-on 为 705.1 s。相比之下，Plain EDA-TS-off、NSGA-II-off 和 MOEA/D-off 的平均运行时间分别为 97.1 s、90.7 s 和 67.3 s。后续定稿应增加同时间预算或同评价次数对比，以区分搜索质量提升与计算开销增加。

### 6.6 消融分析

轻量消融实验覆盖 mk05、mk10 和 mk15，结果如表 3 所示。

**表 3 轻量消融平均结果**

| 变体 | HV ↑ | IGD ↓ | Min total cost ↓ | Min makespan ↓ | Runtime (s) ↓ |
| --- | ---: | ---: | ---: | ---: | ---: |
| Full | \(1.318\times10^7\) | \(1.393\times10^4\) | \(1.851\times10^4\) | 164.1 | 1100.8 |
| No-VC-init | \(1.280\times10^7\) | \(1.409\times10^4\) | \(1.867\times10^4\) | 186.2 | 937.4 |
| No-prior | \(1.324\times10^7\) | \(1.392\times10^4\) | \(1.851\times10^4\) | 162.8 | 1005.9 |
| No-cross-neighbors | \(1.320\times10^7\) | \(1.392\times10^4\) | \(1.851\times10^4\) | 162.3 | 453.9 |
| No-adaptive-neighborhood | \(1.325\times10^7\) | \(1.392\times10^4\) | \(1.851\times10^4\) | 161.4 | 1487.2 |
| No-archive | \(1.318\times10^7\) | \(1.393\times10^4\) | \(1.851\times10^4\) | 163.4 | 1044.9 |

消融结果应谨慎解释，因为该实验仅覆盖 3 个实例和 3 个种子。最稳定的观察是价值链感知初始化的贡献：去除该模块后，平均 HV 从 \(1.318\times10^7\) 降至 \(1.280\times10^7\)，平均 IGD 从 \(1.393\times10^4\) 升至 \(1.409\times10^4\)，平均最低总成本从 \(1.851\times10^4\) 升至 \(1.867\times10^4\)，平均最短 makespan 从 164.1 增至 186.2。这说明在当前实例集上，初始种群能否较早覆盖价值链合理分配结构，对后续搜索质量有直接影响。

其他模块的证据较弱。No-prior、No-cross-neighbors、No-adaptive-neighborhood 和 No-archive 在该轻量实验中没有表现出稳定劣化，部分变体甚至在 HV 或 makespan 上略优于 Full。这并不支持“所有模块均单调增益”的强论断，而更可能说明当前 equal-processing 数据集不足以充分激活跨链先验、跨链邻域和自适应邻域的优势。后续应在跨链时间有优势、链内 SRU 明显拥堵、跨链固定成本较低等场景中扩大消融，以检验这些模块的条件性贡献。

### 6.7 敏感性分析

当前可用敏感性汇总仅覆盖 mk05 的三个随机种子，因此结果用于解释机制趋势，而不作为全实例统计结论。在 cross-on 模式下，跨链固定成本从 0 增至 40 时，平均跨链比例从 0.335 降至 0.179，平均 HV 从 65,288 降至 53,575，平均 IGD 从 274.6 增至 365.0。这表明跨链固定成本能够抑制跨链调用，并削弱跨链资源对前沿质量的贡献。

运输成本比例从 0.8 增至 1.2 时，平均跨链比例从 0.298 降至 0.239，平均 HV 从 61,860 降至 57,102，平均 IGD 从 299.9 增至 335.3。这说明运输成本同样影响跨链协同强度，但其影响弱于跨链时间收益。

跨链时间比例的影响最显著。当跨链时间比例为 0.8 时，平均跨链比例为 0.802，平均最短 makespan 为 71.23，平均 HV 为 76,958；当跨链时间比例为 1.2 时，平均跨链比例降至 0.0037，平均最短 makespan 增至 84.19，平均 HV 降至 50,411。该结果清楚说明，跨链协同只有在跨链资源具有明确时间优势时才会被算法充分利用。这一发现强化了本文的核心解释：跨链机制本质上是成本-工期权衡，而不是简单扩大候选资源集合。

### 6.8 Integrated-mechanism equal-processing 实验验证跨链收益的边界

表 4 给出 integrated-mechanism equal-processing 中等规模实验的统一汇总结果。与 6.2 节正式主实验相比，该实验的运行预算较小，采用 2 个随机种子、种群规模 50 和最大迭代 50；因此，该结果更适合作为机制补充证据，而不应与 5 个种子、种群规模 80、最大迭代 150 的正式主实验直接合并统计。与上一节敏感性结果不同，该数据集保持链内和跨链加工时间等价，因此更适合检验跨链候选扩展是否能够在没有加工时间优势的情况下改善调度。

**表 4 Integrated-mechanism equal-processing 中等规模实验平均结果**

| 算法与模式 | Runs | HV ↑ | IGD ↓ | Min total cost ↓ | Min makespan ↓ | Front size ↑ | Runtime (s) ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| MVC-EDA-TS-on | 30 | 0.6406 | \(1.428\times10^4\) | \(1.538\times10^4\) | 165.1 | 14.0 | 426.3 |
| MVC-EDA-TS-off | 30 | 0.6161 | \(1.428\times10^4\) | \(1.538\times10^4\) | 208.7 | 9.0 | 83.8 |
| NSGA-II-off | 30 | 0.5702 | \(1.626\times10^4\) | \(1.737\times10^4\) | 235.6 | 9.6 | 18.4 |
| MOEA/D-off | 30 | 0.5653 | \(1.618\times10^4\) | \(1.729\times10^4\) | 250.1 | 8.1 | 14.5 |
| Plain EDA-TS-off | 30 | 0.5628 | \(1.555\times10^4\) | \(1.666\times10^4\) | 272.4 | 7.4 | 22.0 |

在 cross-off 算法比较中，MVC-EDA-TS-off 仍然优于三个基线。相对于 NSGA-II-off，MVC-EDA-TS-off 的 HV 提高 8.06%，IGD 降低 12.19%，最低总成本降低 11.43%，最短 makespan 降低 11.42%；相对于 MOEA/D-off，对应改进为 9.00%、11.74%、11.01% 和 16.55%；相对于 Plain EDA-TS-off，对应改进为 9.48%、8.17%、7.64% 和 23.38%。Wilcoxon signed-rank tests 显示，MVC-EDA-TS-off 相对三个 cross-off 基线在 HV、IGD、最低总成本和最短 makespan 上均达到显著优势，调整后 \(p=0.0073\) 或更小，唯一较大的显著比较为相对 NSGA-II-off 的最短 makespan，调整后 \(p=0.0288\)。Friedman ranking 也将 MVC-EDA-TS 排为四项指标第一。这说明，即使在较小运行预算下，价值链感知概率学习和局部搜索仍能稳定改善 Pareto 前沿质量。

在 MVC-EDA-TS 的 on/off 机制比较中，开启跨链带来的收益集中体现在 HV、非支配解规模、负载均衡和工期端，而不是最低成本端。MVC-EDA-TS-on 相对 MVC-EDA-TS-off 的 HV 从 0.6161 提高到 0.6406，增幅为 3.97%，Wilcoxon 调整后 \(p=0.0018\)；最短 makespan 从 208.7 降至 165.1，降幅为 20.89%，调整后 \(p=0.0022\)。同时，平均 front size 从 9.0 增至 14.0，说明 cross-on 扩展了可用的非支配权衡解。按实例统计，15 个实例中有 14 个在 HV 上受益，14 个在最短 makespan 上受益。

然而，该收益并不是全面支配。MVC-EDA-TS-on 和 off 的平均最低总成本均为 \(1.538\times10^4\)，15 个实例的最低总成本均保持不变；IGD 也几乎相同，分别为 14281.8 和 14281.6，差异不显著（调整后 \(p=0.3203\)）。这一结果表明，在 equal-processing 机制实例中，跨链机制主要通过释放链内负载瓶颈来拓展工期端和覆盖范围，而不是创造更低成本解或显著拉近生成前沿与参考前沿的整体距离。

机制指标支持这一解释。cross-on 的平均跨链比例为 0.109，而 cross-off 为 0；平均 SRU 负载标准差从 337.9 降至 216.4，降幅为 35.96%。成本分解显示，cross-on 引入平均 220.2 的跨链固定成本，并使平均运输成本从 90.3 增至 123.0；因此，非支配解集的平均总成本从 15,569.5 增至 16,999.4。也就是说，跨链调度用额外协同成本换取了更短 makespan 和更均衡的 SRU 负载，但并未降低最低成本边界。

该实验也暴露出计算代价。MVC-EDA-TS-on 的平均运行时间为 426.3 s，是 MVC-EDA-TS-off 的 5.1 倍，也显著高于三个 cross-off 基线。停止原因表显示，MVC-EDA-TS-on 有 20 次运行达到 50 次最大迭代，另有 10 次触发 600 s 时间上限，平均完成迭代数为 45.1；其他 cross-off 算法均完成 50 次迭代。因此，integrated-mechanism equal-processing 实验支持“跨链机制可显著改善工期端和负载均衡”的论断，但同时要求在定稿前补充同评价次数或同时间预算实验，以区分机制收益与计算开销差异。

### 6.9 mk14/mk15 聚焦机制案例揭示两类跨链收益路径

mk14/mk15 聚焦机制案例进一步说明，跨链协同的收益来源并不单一。表 5 汇总了 `cross_time_advantage` 与 `intra_congested` 两类场景下 MVC-EDA-TS 的 on/off 平均结果。该实验覆盖 mk14 和 mk15、5 个随机种子，共 40 次运行；每个运行均完成 150 次迭代。

**表 5 mk14/mk15 聚焦机制案例平均结果**

| 场景 | Cross | Runs | HV ↑ | IGD ↓ | Min total cost ↓ | Min makespan ↓ | Cross ratio | SRU load std ↓ | Runtime (s) ↓ |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Cross-time advantage | off | 10 | \(4.035\times10^6\) | \(7.911\times10^3\) | \(4.081\times10^4\) | 307.6 | 0.000 | 284.8 | 401.5 |
| Cross-time advantage | on | 10 | \(8.129\times10^6\) | \(2.431\times10^3\) | \(3.480\times10^4\) | 250.0 | 0.952 | 182.5 | 937.5 |
| Intra-congested | off | 10 | \(3.589\times10^6\) | \(7.914\times10^3\) | \(4.081\times10^4\) | 389.9 | 0.000 | 800.8 | 460.8 |
| Intra-congested | on | 10 | \(3.962\times10^6\) | \(7.914\times10^3\) | \(4.081\times10^4\) | 310.7 | 0.151 | 494.7 | 2282.8 |

在 `cross_time_advantage` 场景中，开启跨链带来了全面收益。MVC-EDA-TS-on 相对 off 的 HV 从 \(4.035\times10^6\) 提高到 \(8.129\times10^6\)，增幅为 101.48%；IGD 从 \(7.911\times10^3\) 降至 \(2.431\times10^3\)，降幅为 69.27%；最低总成本从 \(4.081\times10^4\) 降至 \(3.480\times10^4\)，降幅为 14.72%；最短 makespan 从 307.6 降至 250.0，降幅为 18.73%。按同实例同种子配对统计，cross-on 在 HV、IGD、最低总成本、最短 makespan 和 SRU 负载标准差上均 10 次优于 cross-off。这一结果说明，当跨链 SRU 具有明确加工时间优势时，算法会高强度调用跨链资源；平均跨链比例达到 0.952，SRU 负载标准差也从 284.8 降至 182.5。

相比之下，`intra_congested` 场景展示的是另一种收益路径。由于链内和跨链加工时间相同，cross-on 不降低最低总成本，平均最低总成本保持 \(4.081\times10^4\)；IGD 也几乎不变。但是，cross-on 仍把最短 makespan 从 389.9 降至 310.7，降幅为 20.31%，并将 SRU 负载标准差从 800.8 降至 494.7，降幅为 38.22%。按同实例同种子配对统计，cross-on 在最短 makespan 和 SRU 负载标准差上均 10 次优于 cross-off；HV 也 10 次优于 cross-off，但 IGD 仅 4 次更好、2 次持平、4 次更差。因此，该场景支持的结论不是“跨链全面改善前沿收敛”，而是“在链内拥堵下，少量跨链调用可以显著缓解瓶颈并改善工期端”。其平均跨链比例仅为 0.151，明显低于 `cross_time_advantage` 场景，说明负载缓解型跨链更像定向释放瓶颈，而不是大规模资源迁移。

实例级合并前沿也体现了这种差异。在 `cross_time_advantage` 场景中，mk14 和 mk15 的 on/off 合并非支配前沿分别全部来自 cross-on，说明跨链时间优势足以使 cross-on 解支配链内解。在 `intra_congested` 场景中，mk14 的合并前沿包含 13 个 on-only 点和 3 个 off-only 点，mk15 包含 17 个 on-only 点和 3 个 off-only 点，说明链内调度仍保留少量低成本或局部权衡价值，但 cross-on 成为主要前沿来源。

该案例实验同时强调计算代价。`cross_time_advantage` 中 cross-on 平均运行时间为 937.5 s，是 cross-off 的 2.34 倍；`intra_congested` 中 cross-on 平均运行时间为 2282.8 s，是 cross-off 的 4.95 倍。特别是在拥堵场景中，cross-on 扩大候选 SRU 集合后产生更多可行但相近的负载释放方案，使搜索和档案维护更耗时。因此，该实验强化了本文的边界表述：跨链机制可以通过“时间优势”和“负载缓解”两条路径改善调度，但其收益需要与显著增加的搜索开销一起评价。

## 7 讨论

本文结果表明，将价值链归属引入共享制造调度具有两层意义。第一，它改变了资源可用性的含义。传统供需匹配只回答服务类型是否匹配，而 MVC-SM-DFJSP 进一步回答该匹配发生在链内还是跨链。第二，它为 Pareto 前沿提供了管理解释。前沿上的不同解不仅对应成本和工期的数值差异，也对应平台在价值链之间调动资源的不同程度。

与 Wei 等提出的 SM-DFJSP 供需匹配模型相比，本文的改进点可以概括为“概念拆分、约束扩展和机制解释”三层。概念上，本文将供需类型拆分为业务价值链归属和制造服务类型需求，避免把“订单来自哪条业务链”和“订单需要哪类制造能力”合并为同一标签。约束上，本文在服务类型匹配之外增加链内/跨链候选集和跨链模式开关，使平台可以显式比较链内稳定加工与跨链协同加工。机制上，本文不仅优化成本和工期，还记录跨链流、价值链流入流出和 SRU 负载分布，用于解释跨链协同在什么实例条件下真正改善 Pareto 前沿。

MVC-EDA-TS 的优势主要来自问题知识对搜索空间的约束和引导。与 Plain EDA-TS 的对比尤其重要：Plain EDA-TS 已经能在 IGD 和最低总成本上优于 NSGA-II 与 MOEA/D，说明 EDA-TS 框架本身具备较强的成本压缩和收敛能力；但它在 HV 和最短 makespan 上不足，说明仅有通用 EDA-TS 搜索并不能充分处理 MVC-SM-DFJSP 的多层分配和排程冲突。MVC-EDA-TS 通过价值链感知初始化、价值链先验、跨链/链内局部邻域和非支配解档案，把搜索从单纯成本收敛扩展到更均衡的 Pareto 前沿覆盖。

不过，当前证据也显示跨链协同收益具有明确边界。在正式 2VC/2Type/4SRU equal-processing 数据集中，跨链加工时间与链内加工时间保持一致，跨链主要带来额外运输和固定成本。因此，开启跨链对全局平均结果的提升较小，甚至在部分实例上降低前沿质量。新的 integrated-mechanism equal-processing 实验进一步表明，即使没有跨链加工时间优势，cross-on 仍可通过提高平均跨链比例、降低 SRU 负载标准差和扩大非支配解集来显著改善 HV 与最短 makespan，但这种改善不伴随 IGD 或最低总成本的显著改善，并且带来约 5 倍运行时间开销。mk14/mk15 聚焦机制案例则进一步把跨链收益拆分为两条路径：当跨链加工更快时，cross-on 同时改善前沿质量、成本和工期；当链内 SRU 拥堵但跨链加工时间不变时，cross-on 主要改善 makespan 和负载均衡，而不改变最低成本。三组结果共同说明，跨链机制不是普遍优势开关，而是依赖“链内拥堵、跨链时间优势、协同成本适中和计算预算充足”共同作用的协同能力。

当前工作还存在若干限制。首先，虽然主对比已经补充 Wilcoxon 和 Friedman 检验，但尚未进行同运行时间或同评价次数预算下的公平对比，因此计算开销对性能提升的影响仍需进一步分离，尤其是 integrated-mechanism equal-processing 和 mk14/mk15 机制案例中 cross-on 平均运行时间明显高于 cross-off。其次，消融实验和敏感性实验为轻量设置，当前可用敏感性汇总仅覆盖 mk05，需要扩展到更多实例和随机种子。第三，integrated-mechanism equal-processing 实验仅使用 2 个随机种子和 50 次迭代，适合作为机制证据，但还不足以替代 5 个种子、150 次迭代的正式主实验；mk14/mk15 机制案例虽然使用正式预算和 5 个种子，但只覆盖两个大规模实例。第四，当前模型采用订单级 SRU 分配，尚未考虑工序级跨 SRU 转运。第五，当前为静态确定性调度，尚未考虑动态订单到达、机器故障、质量检验、碳排放和多平台协同。第六，参考文献仍需逐篇核对并补齐正式引用格式。

尽管如此，本文提供了一条清晰的建模路径：先在静态双目标场景下建立价值链协同的可计算框架，再逐步扩展到动态、多目标和更复杂的共享制造场景。这一策略有助于保持模型可解释性和实验可复现性。

## 8 结论

本文提出 MVC-SM-DFJSP，用于刻画共享制造平台中多服务价值链协同下的分布式柔性作业车间双目标调度问题。该模型显式区分订单价值链归属和制造服务类型需求，并通过链内/跨链候选 SRU、运输成本和跨链固定协调成本描述平台资源协同。围绕该模型，本文设计 MVC-EDA-TS，将价值链感知概率学习、跨链协同禁忌搜索、自适应邻域选择和非支配解档案结合，用于求解总成本和最大完工时间之间的 Pareto 折中。

小规模 exact validation 表明，本文的目标函数、跨链约束处理和解码过程能够在可穷举实例上恢复真实非支配前沿，且未产生不可行解。在 MVC-MK01 至 MVC-MK15 的正式主实验和 Plain EDA-TS 基线对比中，MVC-EDA-TS 在 HV、IGD、最低成本和最短 makespan 等指标上整体优于 NSGA-II、MOEA/D 和 Plain EDA-TS，并通过 Wilcoxon signed-rank tests 与 Friedman ranking 获得统计支持。Plain EDA-TS 在 IGD 和最低成本上优于通用基线，但在 makespan 上明显不足，说明 MVC 价值链机制对平衡成本和工期具有额外贡献。跨链协同的收益不是无条件的；在 equal-processing 数据集中，它主要在部分实例上改善 makespan。新的 integrated-mechanism equal-processing 实验进一步显示，MVC-EDA-TS-on 相对 off 可将平均 HV 从 0.6161 提高到 0.6406，并把最短 makespan 从 208.7 降至 165.1，同时使 SRU 负载标准差从 337.9 降至 216.4，但不显著改善 IGD 或最低总成本。mk14/mk15 聚焦机制案例进一步表明，跨链时间优势可带来全面前沿收益，而链内拥堵主要通过较低比例跨链调用改善 makespan 和 SRU 负载均衡。轻量消融结果表明，价值链感知初始化是当前证据中最稳定的正向模块，其他模块仍需在更能激活跨链协同的实例上继续验证。

未来工作将从四个方向推进。第一，补充同时间预算或同评价次数预算下的公平对比。第二，扩展消融、敏感性和机制案例实验，构造更能体现链内拥堵与跨链时间优势的实例。第三，将订单级跨链扩展为工序级跨 SRU 转运，并引入动态订单和设备扰动。第四，将碳排放、服务可靠性和多平台协同纳入更丰富的共享制造调度框架。

## 参考文献（待核对与补全）

1. Shared manufacturing-based distributed flexible job shop scheduling with supply-demand matching. Computers & Industrial Engineering, 2024. DOI: 10.1016/j.cie.2024.109950.
2. An Improved Genetic Algorithm for the Distributed and Flexible Job-shop Scheduling problem. European Journal of Operational Research, 2010. DOI: 10.1016/j.ejor.2009.01.008.
3. The flexible job shop scheduling problem: A review. European Journal of Operational Research, 2024. DOI: 10.1016/j.ejor.2023.05.017.
4. Scheduling in cloud manufacturing: state-of-the-art and research challenges. International Journal of Production Research, 2019. DOI: 10.1080/00207543.2018.1449978.
5. Planning and scheduling shared manufacturing systems: key characteristics, current developments and future trends. International Journal of Production Research, 2025. DOI: 10.1080/00207543.2024.2442549.
6. An efficient memetic algorithm for distributed flexible job shop scheduling problem with transfers. Expert Systems with Applications, 2020. DOI: 10.1016/j.eswa.2020.113721.
7. A hybrid estimation of distribution algorithm for distributed flexible job shop scheduling with crane transportations. Swarm and Evolutionary Computation, 2021. DOI: 10.1016/j.swevo.2021.100861.
8. A hybrid genetic tabu search algorithm for distributed flexible job shop scheduling problems. Journal of Manufacturing Systems, 2023. DOI: 10.1016/j.jmsy.2023.09.002.
9. A learning-driven multi-objective cooperative artificial bee colony algorithm for distributed flexible job shop scheduling problems with preventive maintenance and transportation operations. Computers & Industrial Engineering, 2024. DOI: 10.1016/j.cie.2024.110484.
10. Multi-objective fitness landscape-based estimation of distribution algorithm for distributed heterogeneous flexible job shop scheduling problem. Applied Soft Computing, 2025. DOI: 10.1016/j.asoc.2025.112780.

## 附录 A 证据来源

| 内容 | 项目文件 |
| --- | --- |
| 论文定位与方法口径 | `sm_dfjsp/docs/MVC_SM_DFJSP_双目标论文方法实现文档_2026-06-07.md` |
| 相关文献整理 | `sm_dfjsp/docs/MVC_SM_DFJSP_相关论文整理_2026-06-07.md` |
| 数据集说明 | `sm_dfjsp/data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty/README.md` |
| 主实验元数据 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/main_experiment/run_meta.json` |
| 主实验指标 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/main_experiment/metrics/metrics_summary.csv` |
| Plain EDA-TS 基线 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/plain_edats_off/metrics/metrics_summary.csv` |
| 合并后的对比指标 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/stat_tests/algorithm_off_comparison_metrics.csv` |
| 统计检验 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/stat_tests/stat_tests_summary.md` |
| 小规模精确验证 | `sm_dfjsp/reports/mvc_small_validation/validation_summary.csv` |
| 小规模验证说明 | `sm_dfjsp/docs/MVC_SM_DFJSP_小规模验证说明_2026-06-15.md` |
| 消融实验 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/ablation_light/all_instance_ablation_summary.csv` |
| 敏感性实验 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/sensitivity_light/by_instance/mk05/seed*/sensitivity_summary.csv` |
| mk14/mk15 机制案例数据集 | `sm_dfjsp/data/mvc_mk01_15_2vc4sru_mechanism_vc_load/README.md` |
| mk14/mk15 机制案例元数据 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/mechanism_cases_mk14_mk15_only/run_meta.json` |
| mk14/mk15 机制案例指标 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/mechanism_cases_mk14_mk15_only/metrics/metrics_summary.csv` |
| mk14/mk15 机制案例前沿 | `sm_dfjsp/reports/mvc_mk01_15_formal_80pop_150iter2/mechanism_cases_mk14_mk15_only/pareto/combined_front_plots/summary/per_instance_nd_summary.csv` |
| Integrated-mechanism equal-processing 数据集 | `sm_dfjsp/data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc/README.md` |
| Integrated-mechanism equal-processing 实验状态 | `sm_dfjsp/reports/mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2/experiment_1_2_pipeline_status.json` |
| Integrated-mechanism equal-processing 实验汇总 | `sm_dfjsp/reports/mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2/tables/table_algorithm_performance.csv` |
| Integrated-mechanism equal-processing 跨链分析 | `sm_dfjsp/reports/mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2/tables/table_cross_chain_analysis.csv` |
| Integrated-mechanism equal-processing 统计检验 | `sm_dfjsp/reports/mvc_mk01_15_integrated_mechanism_equalproc_medium_exp1_exp2/stat_tests/stat_tests_summary.md` |
| MVC-EDA-TS 算法 | `sm_dfjsp/src/smdfjsp/mvc_eda_ts/algorithm.py` |
| 概率模型 | `sm_dfjsp/src/smdfjsp/mvc_eda_ts/probability_model.py` |
| 禁忌搜索 | `sm_dfjsp/src/smdfjsp/mvc_eda_ts/tabu_search.py` |
| 调度评价器 | `sm_dfjsp/src/smdfjsp/model/mvc_evaluator.py` |

## 附录 B 投稿前必须补强的内容

1. 增加同运行时间或同评价次数预算下的公平对比。
2. 将轻量消融扩展到 MVC-MK01 至 MVC-MK15 或至少覆盖小、中、大规模实例。
3. 补全敏感性实验的 mk10、mk15 汇总，并将 integrated mechanism 实验扩展到更多随机种子和更充分迭代预算。
4. 将 mk14/mk15 机制案例扩展到更多实例，或把 cross-time-advantage 与 intra-congested 机制纳入全 15 实例正式机制实验。
5. 明确每张图表的编号、标题、数据来源和统计口径。
6. 核对参考文献 DOI、作者、年份、期刊卷期页码。
7. 在正式英文稿中将 Results 与 Discussion 分离，避免把机制解释提前写入结果描述。

## 附录 C 主要论断-证据映射

| 主要论断 | 证据 | 状态 |
| --- | --- | --- |
| MVC-SM-DFJSP 与传统 SM-DFJSP 的核心区别是显式区分价值链归属与服务类型需求 | 方法文档、数据结构、候选 SRU 构造规则和本文第 3 节模型定义 | 已由模型和代码支持 |
| 模型、目标函数和解码器在小规模实例上一致 | 3 个可穷举小规模实例、6 个 cross-off/cross-on 组合、exact coverage=1.0、false_nd_count=0、infeasible_count=0、HV gap=0、IGD=0 | 已由小规模 exact validation 支持 |
| MVC-EDA-TS 在主实验中整体优于 NSGA-II、MOEA/D 和 Plain EDA-TS | 15 实例、5 种子、450 次主实验、75 次 Plain EDA-TS 基线、`stat_tests` 中 Wilcoxon 与 Friedman 结果 | 已由当前结果和统计检验支持 |
| Plain EDA-TS 是有效但不充分的内部基线 | Plain EDA-TS 在 IGD 和最低总成本上优于 NSGA-II/MOEA/D，但在 HV 不显著、最短 makespan 显著较差 | 已由当前结果支持 |
| 跨链协同不是无条件提升，而是依赖成本、时间参数和计算预算 | equal-processing 主实验中的 MVC-EDA-TS on/off 比较、mk05 敏感性实验、integrated-mechanism equal-processing 中等规模实验、mk14/mk15 聚焦机制案例 | 已由多组结果支持，需同预算扩展 |
| 价值链感知初始化有助于低工期区域搜索 | 轻量消融中 No-VC-init 的平均最短 makespan 从 164.1 增至 186.2 | 初步支持，需更多实例验证 |
| Integrated-mechanism equal-processing 数据集中 cross-on 可激活工期端和负载均衡收益 | MVC-EDA-TS-on 相对 off 的 HV 显著提高，最短 makespan 从 208.7 降至 165.1，平均跨链比例为 0.109，SRU 负载标准差从 337.9 降至 216.4；但 IGD 和最低总成本未显著改善 | 已由 15 实例、2 种子中等规模实验支持，需更多种子和同预算验证 |
| 跨链时间优势与链内拥堵激活不同收益路径 | mk14/mk15 机制案例中，cross-time-advantage 场景 cross-on 全面改善 HV、IGD、最低总成本、最短 makespan 和负载标准差；intra-congested 场景主要改善最短 makespan 和 SRU 负载标准差，最低总成本不变 | 已由 2 实例、2 场景、5 种子机制案例支持，需扩展到更多实例 |
| 非支配解档案、自适应邻域和跨链邻域的贡献具有条件性 | 轻量消融中部分去除模块的变体没有稳定劣化 | 证据不足，需更强机制实例验证 |
| MVC-EDA-TS 的计算开销高于通用基线 | 主实验平均 runtime：MVC-EDA-TS-on 为 705.1 s，NSGA-II-on 为 93.8 s，MOEA/D-on 为 69.7 s；integrated-mechanism equal-processing 实验中 MVC-EDA-TS-on 为 426.3 s，MVC-EDA-TS-off 为 83.8 s；mk14/mk15 机制案例中 cross-on 运行时间为 cross-off 的 2.34 至 4.95 倍 | 已由当前结果支持，需同预算对比 |
