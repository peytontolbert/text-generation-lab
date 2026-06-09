# Stage609 Entity Role Answer Residual Dataset

Artifact: `runs/local/artifacts/stage609_entity_role_answer_residual_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage609_entity_role_answer_residual_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Target op: `entity_context`
- Answer-miss source ids: `125`
- Near-miss source ids: `64`
- Repeat failures: `4`
- Repeat near misses: `1`
- Train examples: `22732` -> `23296`
- Eval examples unchanged: `2340`

## Decision

`entity_role_answer_residual_dataset_ready`

## Finding

Stage609 narrows the Stage608 idea to entity_context answer misses on the role-token surface only. It tests whether weak answer contrast can repair local value binding without the global damage seen in broad operation-wide contrast.
