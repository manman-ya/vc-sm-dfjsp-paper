# MVC MK14-MK15 Merged 3VC/2Type/6SRU Equal-Processing Dataset

Generated from `data/mk/mk14_mk15_merged.txt` using the same equal-processing and fixed cross-chain penalty policy as `data/mvc_mk01_15_2vc4sru_equalproc_vcpenalty`, extended to 3 value chains and 6 SRUs.

- Value chains: VC1, VC2, VC3 are assigned by job-id round robin.
- Service types: T1/T2 are assigned by operation-count split.
- SRUs: U1=VC1-T1, U2=VC1-T2, U3=VC2-T1, U4=VC2-T2, U5=VC3-T1, U6=VC3-T2.
- Each job has exactly one intra-chain SRU and two cross-chain SRUs with matching service type.
- Processing time is homogeneous across candidate SRUs: adjusted_processing_time equals the original MK processing time.
- Unit processing cost depends only on the base machine and is identical across SRUs.
- Local transport: transport_time = 2 + job_id % 2, transport_unit_cost = 1.8.
- Cross-chain transport: VC1-VC2 and VC2-VC3 use base time 7; VC1-VC3 uses base time 10; then add job_id % 3.
- Cross-chain fixed costs: VC1-VC2=200.0, VC2-VC3=230.0, VC1-VC3=320.0.
- cross_chain_cost_rate is always 0.0.
- Formal total cost: processing_cost + transport_cost + cross_fixed_cost.
