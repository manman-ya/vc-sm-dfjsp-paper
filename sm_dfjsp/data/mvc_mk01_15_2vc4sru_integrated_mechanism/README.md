# MVC-MK01-15 2VC/2Type/4SRU Integrated Mechanism Dataset

This dataset is generated from `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`
without overwriting the original formal benchmark or the separated mechanism dataset.

## Why this dataset has only 15 instances

The separated mechanism dataset contains two independent scenario families:
`intra_congested` and `cross_time_advantage`. This integrated dataset combines
both mechanisms into one instance per MK source instance, so it can be used as a
single 15-instance mechanism benchmark.

## Integrated design

For each source instance mk01-mk15:

1. Within each service type, jobs are sorted by workload
   `sum(min adjusted_processing_time for each operation)`.
2. The highest-workload jobs are assigned to VC1:
   - mk01-mk05: top 70% per type -> VC1.
   - mk06-mk10: top 75% per type -> VC1.
   - mk11-mk15: top 80% per type -> VC1.
3. SRUs remain fixed:
   - U1=VC1-T1
   - U2=VC1-T2
   - U3=VC2-T1
   - U4=VC2-T2
4. Each job keeps exactly one intra-chain SRU and one same-type cross-chain SRU.
5. Cross-chain processing options are faster:
   - cross adjusted_processing_time = round(original * 0.75)
6. Cross-chain use still has moderate collaboration cost:
   - cross fixed cost = 90.0
   - cross transport time = 4 + job_id % 2
   - cross transport unit cost = 3.5

## Intended interpretation

These instances are not replacements for the fair equal-processing benchmark.
They are mechanism instances designed to make cross-chain scheduling observable:
VC1 owns most high-workload jobs, so U1 and U2 become congested; VC2's same-type
SRUs, U3 and U4, provide both load relief and shorter processing time when
cross-chain is enabled.

## Files

- `manifest.csv`: one row per generated JSON instance.
- `*_integrated_mechanism.json`: one integrated mechanism instance per mk source instance.
