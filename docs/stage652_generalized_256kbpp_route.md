# Stage652 Generalized 256 KBPP Route

Artifact: `runs/local/artifacts/stage652_generalized_256kbpp_route.json`

## Target

Current frontier: `stage651_rank3_residual` at `3.798421037978204` no-filter answer KBPP.

Target: `256.0` generalized no-filter KBPP.

- Multiplier needed: `67.39642536738418`
- Practical doubling rounds: `7`
- 16k verified bits at target: `4167680.0`
- 100M verified bits at target: `25600000000.0`

## Ladder

| Target KBPP | 16k verified bits | Approx flat eval units | 100M verified bits |
|---:|---:|---:|---:|
| 8 | 130240 | 9821 | 800000000 |
| 16 | 260480 | 18388 | 1600000000 |
| 32 | 520960 | 34555 | 3200000000 |
| 64 | 1041920 | 65155 | 6400000000 |
| 128 | 2083840 | 123225 | 12800000000 |
| 256 | 4167680 | 233690 | 25600000000 |

## Algorithm

1. Measure current no-filter KBPP and surface ceiling.
2. Expand generalized entropy before training if the ceiling cannot support the next 2x.
3. Use compact selectors for binding identity.
4. Collision-condition deterministic keys so filters do not solve the task alone.
5. Train initialized tiny retrieval geometry.
6. Mine train-side rank-2/3 residuals and replay only local near misses.
7. Accept only no-filter held-out generalized KBPP.
8. Sweep 1k through 100M after every accepted rung.

## Next Stage

`stage653_generalized_8kbpp_surface`

Minimum 16k verified bits: `130240`.

Approx flat eval units: `9821`.

The next surface must mix facts, relations, compositions, procedures, abstractions, and counterfactual negatives. It should not be a larger lookup-only answer-card set.
