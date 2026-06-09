# Stage601 Entity Field Context

Artifact: `runs/local/artifacts/stage601_entity_field_context_summary.json`

## Result

Stage601 converted `entity_context` into field-level answer cards and continued Stage599 for `300` steps with value-anchor weight `0.05` on op ID `10`.

No-filter exact/answer moved from `0.8628205128205129` / `0.8841880341880342` to `0.8662393162393163` / `0.8858974358974359`.

Entity-context field exact/answer moved from `0.4618055555555556` / `0.4895833333333333` to `0.4826388888888889` / `0.5104166666666666`.

Hard-filter exact/answer stayed `0.994017094017094` / `0.9948717948717949`, while corrections moved from `307` to `299`.

## Decision

`accepted_as_entity_schema_probe_not_global_collision_frontier`

## Finding

Field-level entity context is a better schema than whole-entity context for collision learning: Stage599 already improves from the old whole-card entity-context exact score, and Stage601 adds another small no-filter gain on entity_context while reducing hard-filter corrections. It is not a new global collision frontier because some non-target operation margins regress. The next route should keep field-level entity cards but mix Stage596 replay or lower the entity-only anchor to avoid direct_fact/set tradeoffs.
