# MVC MK14-MK15 Merged Unbalanced VC1-Load Dataset

Generated from `data/mk/mk14_mk15_merged.txt`.

This scenario keeps the original 60 jobs, 15 base machines, 2 service types, and 6 SRUs, but changes value-chain ownership to create a deliberately congested VC1:

- VC1: 36 jobs, split as 18 T1 and 18 T2.
- VC2: 12 jobs, split as 6 T1 and 6 T2.
- VC3: 12 jobs, split as 6 T1 and 6 T2.
- The global type totals remain balanced: 30 T1 and 30 T2.
- Heavy jobs are assigned preferentially to VC1, making U1=VC1-T1 and U2=VC1-T2 congested in cross-chain-off mode.
- Processing times and processing costs remain equal-processing: each candidate SRU copies the original MK base processing times and machine costs.
- Cross-chain fixed costs remain: VC1-VC2=200.0, VC2-VC3=230.0, VC1-VC3=320.0; variable rate is 0.0.
