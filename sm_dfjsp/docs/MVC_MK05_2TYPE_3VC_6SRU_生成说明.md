# MK05 MVC-SM-DFJSP 2类型实例生成说明

本文档说明 `data/mvc_sm_dfjsp/mk05_mvc_3vc_6sru.json` 的生成逻辑。该文件由 `scripts/build_mk05_mvc_instance.py` 从 `data/mk05.txt` 构造得到。

## 基本规模

- 源实例：`mk05`
- 问题类型：`MVC-SM-DFJSP`
- 订单数：15
- 基础机器数：4，即 `M0..M3`
- 价值链数：3，即 `VC1..VC3`
- 类型数：2，即 `T1..T2`
- SRU 数：6，即 `U1..U6`
- 动态性：静态实例，所有订单 `release_time=0`
- 随机种子：`20260428`

## 价值链划分

价值链按订单编号连续划分：

| 价值链 | 订单 |
| --- | --- |
| `VC1` | `J1,J2,J3,J4,J5` |
| `VC2` | `J6,J7,J8,J9,J10` |
| `VC3` | `J11,J12,J13,J14,J15` |

## 两类型划分

类型按 `mk05` 原始工序数划分：

| 类型 | 含义 | 规则 | 订单 |
| --- | --- | --- | --- |
| `T1` | 短流程件 | 工序数 `<=6` | `J1,J2,J5,J7,J12` |
| `T2` | 中长流程件 | 工序数 `>=7` | `J3,J4,J6,J8,J9,J10,J11,J13,J14,J15` |

该划分将原来的 3 类型压缩为 2 类型，同时保留 `mk05` 原始工序数量差异。

## SRU 布局

每条价值链固定配置 2 个 SRU，分别覆盖 `T1` 和 `T2`。因此任意订单都至少有一个“同价值链、同类型”的候选 SRU。

| SRU | 价值链 | 类型 | 效率系数 | 成本系数 |
| --- | --- | --- | --- | --- |
| `U1` | `VC1` | `T1` | `1.00` | `1.00` |
| `U2` | `VC1` | `T2` | `0.95` | `1.10` |
| `U3` | `VC2` | `T1` | `0.90` | `1.20` |
| `U4` | `VC2` | `T2` | `1.05` | `0.95` |
| `U5` | `VC3` | `T2` | `0.92` | `1.15` |
| `U6` | `VC3` | `T1` | `1.10` | `0.90` |

每个 SRU 都复制基础机器 `M0..M3`，生成全局机器编号，例如 `U1_M0`、`U1_M1`。

## 候选 SRU 规则

候选 SRU 按类型确定：

| 类型 | 候选 SRU |
| --- | --- |
| `T1` | `U1,U3,U6` |
| `T2` | `U2,U4,U5` |

订单的 `candidate_srus` 为其类型对应的全部 SRU。然后再按订单所属价值链拆分：

- `intra_chain_srus`：候选 SRU 中与订单同价值链的 SRU。
- `cross_chain_srus`：候选 SRU 中与订单不同价值链的 SRU。

由于每条价值链都有一个 `T1` SRU 和一个 `T2` SRU，因此所有订单都满足：

```text
len(intra_chain_srus) >= 1
```

也就是说，每个订单都可以选择同价值链、同类型 SRU，不再存在必须跨价值链加工的订单。

## 加工选项生成

对每个订单的每道工序：

1. 从 `mk05.txt` 保留原始可选基础机器和基础加工时间。
2. 对该订单的每个候选 SRU 复制一份加工选项。
3. 对每个加工选项计算调整加工时间：

```text
adjusted_processing_time = ceil(base_processing_time * sru_efficiency_factor * random_noise)
random_noise ~ Uniform(0.95, 1.05)
```

4. 单位加工成本由基础机器成本乘以 SRU 成本系数得到：

```text
unit_processing_cost = base_machine_cost * sru_cost_factor
```

基础机器单位成本为：

| 基础机器 | 单位成本 |
| --- | --- |
| `M0` | `6.0` |
| `M1` | `5.0` |
| `M2` | `7.0` |
| `M3` | `8.0` |

## 运输与跨链成本

订单到候选 SRU 的运输时间按订单价值链和 SRU 价值链查表，并加入整数扰动：

```text
transport_time = base_transport_time[job_vc][sru_vc] + randint(0, 2)
transport_cost = transport_time * 3.0
```

基础运输时间矩阵：

| From / To | `VC1` | `VC2` | `VC3` |
| --- | ---: | ---: | ---: |
| `VC1` | 3 | 9 | 12 |
| `VC2` | 10 | 3 | 8 |
| `VC3` | 11 | 7 | 3 |

若订单和 SRU 不在同一价值链，则标记为跨链，并增加跨链协同成本参数：

```text
cross_chain_fixed_cost = 20.0
cross_chain_cost_rate = 0.05
estimated_cross_chain_cost = 20.0 + 0.05 * estimated_processing_cost
```

同价值链 SRU 的跨链成本为 0。

## 校验规则

生成脚本会校验：

- `n_types=2`
- `n_value_chains=3`
- `n_srus=6`
- 每个订单候选 SRU 与订单类型一致
- 每个订单至少有一个同价值链同类型 SRU
- 每个 SRU 包含 4 台机器
- 每道工序的基础可选机器和加工时间与 `mk05.txt` 一致
- 每道工序在每个候选 SRU 上都有完整加工选项
- 运输时间和运输成本均为正
- 跨链标记与订单/SRU 价值链关系一致

## 生成命令

在 `sm_dfjsp` 目录下执行：

```powershell
D:\App\miniconda3\envs\sm_dfjsp\python.exe scripts/build_mk05_mvc_instance.py --input data/mk05.txt --output data/mvc_sm_dfjsp/mk05_mvc_3vc_6sru.json --seed 20260428
```

生成后脚本会打印摘要，并输出：

```text
validation: PASSED
```

