# Stage610 Entity Selector Tokens Dataset

Artifact: `runs/local/artifacts/stage610_entity_selector_tokens_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage610_entity_selector_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Changed train examples: `2272`
- Changed eval examples: `288`
- Eval selector field counts: `{'capital': 36, 'currency': 36, 'continent': 36, 'owner': 36, 'status': 36, 'priority': 36, 'tool': 36, 'risk': 36}`

## Decision

`entity_selector_token_dataset_ready`

## Finding

Stage610 keeps the Stage607 role-token schema and adds repeated entity+field selector markers to entity_context query/doc text. This tests whether the remaining role-token failures are selector weighting failures before changing the loss.
