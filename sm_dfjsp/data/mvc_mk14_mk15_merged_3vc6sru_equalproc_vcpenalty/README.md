# MVC-MK14-MK15-Merged 3VC/2Type/6SRU Equal-Processing Dataset

Generated from `mk14_mk15_merged.txt` using the same construction policy as the MVC-MK01-15 2VC/4SRU equalproc-vcpenalty dataset, extended to 3 value chains.

- Value chains: VC1, VC2, and VC3 are fixed order-level ownership labels assigned by job-id round robin.
- Service types: T1/T2 are assigned by operation-count split.
- SRUs: U1=VC1-T1, U2=VC1-T2, U3=VC2-T1, U4=VC2-T2, U5=VC3-T1, U6=VC3-T2.
- Each job has exactly one intra-chain SRU and two cross-chain SRUs with matching service type.
- Processing time is homogeneous across candidate SRUs: adjusted_processing_time equals the original MK processing time.
- Unit processing cost depends only on the base machine and is identical across SRUs.
- Local transport: transport_time = 2 + job_id % 2, transport_unit_cost = 1.8.
- Cross-chain transport: transport_time = 7 + job_id % 3, transport_unit_cost = 4.8.
- Cross-chain fixed cost is 200.0; cross_chain_cost_rate is always 0.0.
- Formal total cost: processing_cost + transport_cost + cross_fixed_cost.
