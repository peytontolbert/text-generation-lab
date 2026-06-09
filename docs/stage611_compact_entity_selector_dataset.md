# Stage611 Compact Entity Selector Dataset

Artifact: `runs/local/artifacts/stage611_compact_entity_selector_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage611_compact_entity_selector_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Changed train examples: `2272`
- Changed eval examples: `288`
- Eval selector field counts: `{'capital': 36, 'currency': 36, 'continent': 36, 'owner': 36, 'status': 36, 'priority': 36, 'tool': 36, 'risk': 36}`

## Decision

`compact_entity_selector_dataset_ready`

## Finding

Stage611 compresses Stage610's selector to a single entity-field pair marker. It tests whether selector weighting, rather than repeated domain/entity/field spelling, carries the Stage610 KBPP gain.
