# MVC-MK01-15 2VC/2Type/4SRU Mechanism Dataset with Value-Chain Load Skew

This dataset is generated from `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`
without overwriting the original formal benchmark.

## Purpose

The formal equal-processing dataset assigns jobs almost evenly to VC1 and VC2.
That design is suitable for a fair baseline comparison, but it weakly activates
cross-chain scheduling because the intra-chain SRUs are not strongly congested.
This dataset adds mechanism-oriented instances that deliberately create
intra-chain load imbalance or cross-chain processing-time advantage.

## Common structure

- Value chains: VC1 and VC2.
- Service types: T1 and T2.
- SRUs: U1=VC1-T1, U2=VC1-T2, U3=VC2-T1, U4=VC2-T2.
- Each job keeps exactly one intra-chain SRU and one same-type cross-chain SRU.
- All jobs keep release_time = 0 and one-job-one-SRU hard assignment.

## Scenario 1: intra_congested

Within each service type, jobs are sorted by workload
`sum(min adjusted_processing_time for each operation)`.
The highest-workload jobs are assigned to VC1 and the remaining jobs to VC2:

- mk01-mk05: top 70% per type -> VC1.
- mk06-mk10: top 75% per type -> VC1.
- mk11-mk15: top 80% per type -> VC1.

This makes U1 and U2 the congested intra-chain SRUs, while U3 and U4 become
same-type cross-chain relief resources. Processing times remain equal across
candidate SRUs. Cross-chain transport and fixed cost are moderated:

- cross fixed cost = 80.0
- cross transport time = 4 + job_id % 2
- cross transport unit cost = 3.2

## Scenario 2: cross_time_advantage

The original balanced value-chain assignment is kept, but cross-chain processing
options are faster:

- cross adjusted_processing_time = round(original * 0.75)
- cross fixed cost = 120.0
- cross transport time = 5 + job_id % 2
- cross transport unit cost = 4.0

This scenario tests whether the algorithm trades additional collaboration cost
for shorter makespan when cross-chain SRUs have a real time advantage.

## Files

- `manifest.csv`: one row per generated JSON instance.
- `README.md`: this design description.
- `*_intra_congested.json`: value-chain-load-skew mechanism instances.
- `*_cross_time_advantage.json`: cross-chain-time-advantage mechanism instances.
