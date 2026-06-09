# Stage605 Entity Answer Residual Dataset

Artifact: `runs/local/artifacts/stage605_entity_answer_residual_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage605_entity_answer_residual_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target op: `entity_context`
- Answer-miss source ids: `135`
- Near-miss source ids: `63`
- Repeat failures: `6`
- Repeat near misses: `1`
- Train examples: `22732` -> `23605`
- Eval examples unchanged: `2340`

## Decision

`entity_answer_residual_dataset_ready`

## Finding

Stage605 narrows residual replay to entity_context answer misses only, avoiding the direct_fact exact-miss replay that damaged Stage604.
