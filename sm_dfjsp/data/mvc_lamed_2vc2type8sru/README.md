# MVC-LAMED 2VC/2Type/8SRU Integrated Mechanism Equal-Processing Dataset

Generated from `data/lamed` using the integrated-mechanism construction policy
of `data/mvc_mk01_15_2vc4sru_integrated_mechanism_equalproc`, extended to eight
SRUs so that cross-off keeps two intra-chain same-type choices per job.

## Source instances

- `la31-la35`: 30 jobs, 10 machines, 300 operations per instance.
- `sm03_1`: 50 jobs, 20 machines, 250 operations.

## Integrated mechanism design

For each source instance:

1. Jobs are split into T1/T2 by operation-count order.
2. Within each service type, jobs are sorted by workload:
   `sum(min processing time for each operation)`.
3. The top 70% workload jobs in each service type are assigned to VC1; the rest
   are assigned to VC2. This creates VC1 load pressure while keeping VC2 non-empty.
4. SRUs are fixed:
   - U1,U5 = VC1-T1
   - U2,U6 = VC1-T2
   - U3,U7 = VC2-T1
   - U4,U8 = VC2-T2
5. Each job has two intra-chain same-type SRUs and two cross-chain same-type SRUs.
6. Processing options are equal across candidate SRUs:
   - adjusted processing time equals the source processing time.
   - unit processing cost depends only on base machine and is identical across SRUs.
7. Cross-chain use has moderate collaboration cost:
   - cross fixed cost = 90.0
   - cross transport time = 4 + job_id % 2
   - cross transport unit cost = 3.5

## Intended interpretation

These are mechanism instances, not replacements for the balanced formal benchmark.
They test whether cross-chain scheduling can release overloaded VC1 SRUs without
introducing artificial cross-chain processing-time advantages. The eight-SRU
extension also prevents cross-off from degenerating to a single feasible SRU per
job.

## Files

- `manifest.csv`: one row per generated instance.
- `*_integrated_mechanism.json`: generated MVC-SM-DFJSP instances.
