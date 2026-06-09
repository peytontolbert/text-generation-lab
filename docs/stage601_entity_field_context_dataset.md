# Stage601 Entity Field Context Dataset

Artifact: `runs/local/artifacts/stage601_entity_field_context_dataset.json`

Dataset manifest: `runs/local/tmp/pocketpal_stage601_entity_field_context_seed461/agentkernel_lite_encdec_dataset_manifest.json`

## Result

- Fields: `capital, currency, continent, owner, status, priority, tool, risk`
- Train entity rows: `284` -> `2272`
- Eval entity rows: `36` -> `288`
- Eval field collision rows: `240`
- Eval mean/max candidate count: `1.894736842105263` / `3`

## Decision

`entity_field_context_probe_ready`

## Finding

Stage601 converts entity_context from whole-entity cards into compact field-level answer cards. The exact hard filter still sees multiple same-domain/same-field candidates, so the model must use the entity token to resolve the answer instead of relying on a singleton key.
