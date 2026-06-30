# MVC-MK01-15 2VC/2Type/4SRU Equal-Processing Dataset

Generated from MK/FJSP benchmark files using the same construction policy as the MVC-LA 2VC/4SRU equalproc dataset.

- Value chains: VC1 and VC2 are fixed order-level ownership labels assigned by job-id round robin.
- Service types: T1/T2 are assigned by operation-count split.
- SRUs: U1=VC1-T1, U2=VC1-T2, U3=VC2-T1, U4=VC2-T2.
- Each job has exactly one intra-chain SRU and one cross-chain SRU with matching service type.
- Processing time is homogeneous across candidate SRUs: adjusted_processing_time equals the original MK processing time.
- Unit processing cost depends only on the base machine and is identical across SRUs.
- Local transport: transport_time = 2 + job_id % 2, transport_unit_cost = 1.8.
- Cross-chain transport: transport_time = 7 + job_id % 3, transport_unit_cost = 4.8.
- Cross-chain fixed cost is 200.0; cross_chain_cost_rate is always 0.0.
- Formal total cost: processing_cost + transport_cost + cross_fixed_cost.
