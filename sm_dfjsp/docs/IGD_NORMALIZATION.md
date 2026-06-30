# MVC-SM-DFJSP IGD Normalization

From 2026-06-21 onward, every formal `igd` field in this project means
min-max normalized inverted generational distance. The value is dimensionless
and smaller is better.

The former objective-space distance is retained as `raw_igd` for audit only.
Do not mix `igd` and `raw_igd` in tables, statistical tests, rankings or paper
claims.

## Why normalization is required

MVC-SM-DFJSP uses total cost and makespan as objectives. Their units and ranges
differ, and MK01-MK15 also have different problem scales. Raw Euclidean distance
therefore gives more weight to the objective with the larger numerical range
and makes large instances dominate cross-instance averages.

## Formal definition

For each problem instance, pool every Pareto front that will be compared across
algorithms, modes, seeds and ablation or sensitivity variants. Build one shared
non-dominated reference front and shared objective bounds:

```text
lower_d = min objective_d
upper_d = max objective_d
span_d  = max(upper_d - lower_d, 1.0)
```

Normalize both the evaluated front and the reference front with the same bounds:

```text
z_d = (objective_d - lower_d) / span_d
```

Then compute IGD in normalized space:

```text
igd = mean_{r in normalized_reference}
      min_{a in normalized_front} EuclideanDistance(r, a)
```

Bounds are shared within one instance, not across different MK instances. This
keeps algorithm comparisons fair while preventing instance size from determining
the metric magnitude.

## Output fields

```text
igd      = normalized, dimensionless IGD used for formal analysis
raw_igd  = original objective-space IGD retained for audit
```

Small exact validation uses the same rule:

```text
exact_igd      = normalized IGD
raw_exact_igd  = original objective-space IGD
```

## Code paths

Core implementation:

```text
sm_dfjsp/src/smdfjsp/metrics/multiobjective.py
```

Public functions:

```text
igd()
normalized_igd()
raw_igd()
```

MVC experiment aggregation:

```text
sm_dfjsp/scripts/mvc_experiment_utils.py
```

Exact validation:

```text
sm_dfjsp/scripts/run_mvc_small_exact_validation.py
```

## Reporting text

English:

```text
IGD denotes the inverted generational distance computed after per-instance
min-max normalization with shared objective bounds; smaller is better.
```

Chinese:

```text
本文报告的 IGD 均使用同一实例内所有待比较前沿的共享目标上下界进行
min-max 归一化后计算，为无量纲距离，数值越小表示生成前沿越接近统一参考前沿。
```
