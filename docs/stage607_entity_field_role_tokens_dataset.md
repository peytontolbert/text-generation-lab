# Stage607 Entity Field Role Tokens Dataset

Artifact: `runs/local/artifacts/stage607_entity_field_role_tokens_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage607_entity_field_role_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Changed train examples: `2272`
- Changed eval examples: `288`
- Eval role counts: `{'capital': 36, 'currency': 36, 'continent': 36, 'owner': 36, 'status': 36, 'priority': 36, 'tool': 36, 'risk': 36}`

## Decision

`entity_field_role_token_dataset_ready`

## Finding

Stage607 keeps Stage602's balanced field-level schema but adds explicit repeated FIELD_ROLE tokens to entity_context query/doc text. This targets the Stage606 cross-field confusion without changing hard-filter keys.
