# MVC-SM-DFJSP HV Normalization

From 2026-06-16 onward, the `hv` field in MVC-SM-DFJSP experiment outputs means normalized hypervolume. Algorithm comparisons, mechanism comparisons, statistical tests, tables, and figures should use this normalized `hv` value.

The unnormalized objective-space area is retained only for audit as `raw_hv`. Do not use `raw_hv` as the formal comparison metric.

## Rationale

The old HV was computed directly on raw objective values:

```text
HV ~= cost_unit * time_unit
```

When total cost is in the tens of thousands and makespan is in the hundreds, the raw area can naturally reach tens of millions. That number is scale-dependent and has no direct percentage interpretation.

Normalized HV maps each objective to a shared min-max range and divides by the reference hyper-rectangle volume. The resulting value is dimensionless and normally lies in `[0, 1]`; larger is better.

## Definition

For all Pareto fronts being compared in the same experiment batch, compute shared objective bounds:

```text
lower_d = min objective_d
upper_d = max objective_d
span_d = max(upper_d - lower_d, 1.0)
```

Normalize objective points and the dominated reference point using the same bounds:

```text
z_d = (objective_d - lower_d) / span_d
ref_z_d = (reference_d - lower_d) / span_d
```

The reference point still uses the existing dominated-reference rule:

```text
reference_d = max_d + 0.1 * max(max_d - min_d, 1.0)
```

Then compute minimization HV in normalized space and divide by the normalized reference rectangle volume:

```text
hv = HV(normalized_front, normalized_reference)
     / product(normalized_reference_d)
```

## Code Paths

Core metric implementation:

```text
sm_dfjsp/src/smdfjsp/metrics/multiobjective.py
```

Relevant functions:

```text
objective_bounds()
normalize_front()
normalized_reference_point()
normalized_hypervolume()
```

Experiment aggregation:

```text
sm_dfjsp/scripts/mvc_experiment_utils.py
```

`summarize_metrics()` now outputs:

```text
hv      = normalized_hypervolume(...)
raw_hv  = hypervolume(...)
```

Small exact validation also reports normalized HV gap:

```text
sm_dfjsp/scripts/run_mvc_small_exact_validation.py
```

## Reporting Text

Use this wording in reports and papers:

```text
HV refers to normalized hypervolume; larger is better.
```

Chinese wording:

```text
本文报告的 HV 均为基于统一目标范围和统一参考点计算的归一化 Hypervolume，取值为无量纲比例值，越大表示 Pareto 前沿覆盖越充分。
```
