# Stage602 Entity Field Balanced Replay Dataset

Artifact: `runs/local/artifacts/stage602_entity_field_balanced_replay_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage602_entity_field_balanced_replay_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target replay ops: `direct_fact, set_intersection_member`
- Extra copies per target train row: `1`
- Added train examples: `3777`
- Train examples: `18955` -> `22732`
- Eval examples unchanged: `2340`

## Decision

`entity_field_balanced_replay_dataset_ready`

## Finding

Stage602 keeps the Stage601 field-level entity schema and rebalances the two operations that lost margin during the entity-only continuation: direct_fact and set_intersection_member.
