# MVC-SM-DFJSP HV 归一化说明

## 结论

从 2026-06-16 起，MVC-SM-DFJSP 实验结果中的 `hv` 字段统一表示归一化 Hypervolume，后续算法比较、机制比较、统计检验、表格和图均按归一化 HV 评价。

旧的未归一化面积值不再作为主评价指标。为便于追溯，实验汇总仍额外输出 `raw_hv` 字段。

## 为什么修改

原始 HV 直接在 `total_cost` 和 `makespan` 的原始量纲上计算面积：

```text
HV ≈ cost_unit × time_unit
```

因此当总成本范围达到数万、完工时间范围达到数百时，HV 很容易达到千万量级。这个数值本身没有直观比例含义，也不适合跨数据集或跨实例规模直接解释。

归一化 HV 将目标值压缩到统一尺度，并除以参考超矩形体积，使指标变成无量纲比例值。这样 `hv` 越接近 1，表示当前前沿覆盖的参考目标空间比例越高；`hv` 越接近 0，表示覆盖越弱。

## 归一化方法

对同一批需要比较的 Pareto front，先合并所有目标点，计算每个目标维度的全局上下界：

```text
lower_d = min objective_d
upper_d = max objective_d
span_d = max(upper_d - lower_d, 1.0)
```

原始目标点和参考点使用同一组上下界归一化：

```text
z_d = (objective_d - lower_d) / span_d
ref_z_d = (reference_d - lower_d) / span_d
```

参考点仍使用原有规则：

```text
reference_d = max_d + 0.1 * max(max_d - min_d, 1.0)
```

随后在归一化空间计算 minimization HV，并除以参考超矩形体积：

```text
normalized_hv = HV(normalized_front, normalized_reference)
                / product(normalized_reference_d)
```

因此主评价字段 `hv` 是无量纲归一化值；`raw_hv` 是旧的原始量纲面积值。

## 代码位置

归一化 HV 的核心实现位于：

```text
sm_dfjsp/src/smdfjsp/metrics/multiobjective.py
```

相关函数：

```text
objective_bounds()
normalize_front()
normalized_reference_point()
normalized_hypervolume()
```

主实验汇总入口位于：

```text
sm_dfjsp/scripts/mvc_experiment_utils.py
```

其中 `summarize_metrics()` 现在输出：

```text
hv      = normalized_hypervolume(...)
raw_hv  = hypervolume(...)
```

小规模 exact validation 的 `exact_hv_gap` 也使用归一化 HV 差值，入口位于：

```text
sm_dfjsp/scripts/run_mvc_small_exact_validation.py
```

## 结果解释

后续报告中应写：

```text
HV refers to normalized hypervolume; larger is better.
```

中文表述建议：

```text
本文报告的 HV 均为基于统一目标范围和统一参考点计算的归一化 Hypervolume，取值为无量纲比例值，越大表示 Pareto 前沿覆盖越充分。
```

如果需要复核历史量纲面积，可查看 `raw_hv`，但不要用 `raw_hv` 作为正式比较指标。
