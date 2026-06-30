# MVC-SM-DFJSP 小规模精确验证说明

生成日期：2026-06-15

## 1. 验证目的

本验证用于支撑 `MVC_SM_DFJSP_后续完善工作清单_2026-06-11.md` 中的 2.1“小规模精确验证”。目标是确认 MVC-SM-DFJSP 的解码器、目标函数、cross-off/cross-on 约束处理、成本分解和调度可行性在可穷举小规模实例上一致。

## 2. 执行命令

```bash
python scripts/run_mvc_small_exact_validation.py
```

运行参数记录在：

```text
reports/mvc_small_validation/run_meta.json
```

本次运行使用：

```text
cross modes: off,on
seeds: 20260428,20260429,20260430
popsize: 40
max_iter: 80
time_limit: 60.0
local_search_steps: 6
max_exact_evaluations: 1000000
```

## 3. 输入与输出

生成的小规模实例：

```text
data/mvc_small_validation/mvc_small_01.json
data/mvc_small_validation/mvc_small_02.json
data/mvc_small_validation/mvc_small_03.json
```

验证报告：

```text
reports/mvc_small_validation/exact_front.csv
reports/mvc_small_validation/algorithm_front.csv
reports/mvc_small_validation/validation_summary.csv
reports/mvc_small_validation/validation_summary.md
reports/mvc_small_validation/cost_audit.csv
reports/mvc_small_validation/schedule_audit.csv
reports/mvc_small_validation/run_meta.json
```

## 4. 汇总结果

| Instance | Cross | Exact evaluations | Exact front | Algorithm front | Coverage | False ND | Infeasible | HV gap | IGD |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| mvc_small_01 | off | 3 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_01 | on | 24 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_02 | off | 9216 | 2 | 2 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_02 | on | 147456 | 2 | 2 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_03 | off | 192 | 1 | 1 | 1.0 | 0 | 0 | 0 | 0 |
| mvc_small_03 | on | 6144 | 3 | 3 | 1.0 | 0 | 0 | 0 | 0 |

## 5. 审计结论

1. exact enumeration 未产生不可行解，`exact_infeasible_count=0`。
2. MVC-EDA-TS 在 6 个 instance/mode 组合中均恢复 exact nondominated front，`exact_coverage=1.0`。
3. 算法输出未包含伪非支配点，`false_nd_count=0`。
4. `exact_hv_gap=0` 且 `exact_igd=0`，说明小预算算法前沿与 exact front 在目标值层面一致。
5. `schedule_audit.csv` 中 `machine_no_overlap_global=True` 且 `precedence_ok_global=True`，支持机器不重叠与工序 precedence 约束。
6. `cost_audit.csv` 输出了每个审计解的 processing cost、transport cost、cross fixed cost、job completion 和 transport time，可用于附录中的成本与解码一致性说明。

## 6. 论文可用表述

为验证数学模型、目标函数和解码过程的一致性，本文构造 3 个可穷举的小规模 MVC-SM-DFJSP 实例，并分别在 cross-off 与 cross-on 模式下枚举 UA、OS 和 MS 组合，提取真实 Pareto 前沿。结果表明，MVC-EDA-TS 在全部 6 个 instance/mode 组合中均恢复真实非支配前沿，未产生不可行解或伪非支配解，且相对于 exact front 的 HV gap 与 IGD 均为 0。这一结果验证了本文解码器、成本计算、跨链约束处理和调度可行性检查的一致性。
