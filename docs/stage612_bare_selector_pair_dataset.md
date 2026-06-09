# Stage612 Bare Selector Pair Dataset

Artifact: `runs/local/artifacts/stage612_bare_selector_pair_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage612_bare_selector_pair_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Changed train examples: `2272`
- Changed eval examples: `288`
- Eval selector field counts: `{'capital': 36, 'currency': 36, 'continent': 36, 'owner': 36, 'status': 36, 'priority': 36, 'tool': 36, 'risk': 36}`

## Decision

`bare_selector_pair_dataset_ready`

## Finding

Stage612 removes the explicit ENTITY_SELECTOR label from Stage611. It tests whether the compact pair key alone is enough to preserve selector weighting while reducing token cost.
