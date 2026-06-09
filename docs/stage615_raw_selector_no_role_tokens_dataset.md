# Stage615 Raw Selector No Role Tokens Dataset

Artifact: `runs/local/artifacts/stage615_raw_selector_no_role_tokens_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage615_raw_selector_no_role_tokens_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Changed train examples: `2272`
- Changed eval examples: `288`
- Eval selector field counts: `{'capital': 36, 'currency': 36, 'continent': 36, 'owner': 36, 'status': 36, 'priority': 36, 'tool': 36, 'risk': 36}`

## Decision

`raw_selector_no_role_tokens_dataset_ready`

## Finding

Stage615 tests the raw entity|field selector without FIELD_ROLE tokens to isolate the minimal selector signal.
