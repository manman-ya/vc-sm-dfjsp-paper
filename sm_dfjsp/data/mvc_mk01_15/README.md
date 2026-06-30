# MVC-SM-DFJSP Dataset

Generated from MK/FJSP benchmark files.

- Value chains represent fixed order-level business ownership.
- Service types represent fixed order-level manufacturing demand classes.
- All SRUs are open to shared manufacturing collaboration.
- `cross_chain_allowed` is an experiment mode, not a data openness field.
- Intra-chain choices and cross-chain choices must both match service type.
- Transport cost is generated as `transport_time * 3.0`.
- Cross-chain collaboration cost uses fixed cost `20.0` and variable rate `0.05`.
