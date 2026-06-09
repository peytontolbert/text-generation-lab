# Stage598 Collision Continuation

Artifact: `runs/local/artifacts/stage598_collision_continuation_summary.json`

## Result

| run | steps | no-filter exact | no-filter answer | hard-filter corrections |
|---|---:|---:|---:|---:|
| `stage525_baseline_on_stage596` | `2400` | `0.8836206896551724` | `0.9104406130268199` | `237` |
| `stage597_collision_300step` | `2700` | `0.8931992337164751` | `0.914272030651341` | `217` |
| `stage598_collision_600step` | `3000` | `0.9008620689655172` | `0.9204980842911877` | `201` |

## Decision

`accepted_as_collision_probe_best_so_far`

## Finding

A second 300-step continuation keeps improving the collision-conditioned no-filter score and further reduces deterministic hard-filter corrections. This confirms the Stage596 probe is measuring learnable neural collision resolution, not just lookup-key access. The gap remains large on direct_fact/entity_context/two_hop, so the next gain should target those collision families with operation-balanced replay or value-anchor supervision.
