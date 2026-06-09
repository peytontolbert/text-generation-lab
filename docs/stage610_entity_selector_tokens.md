# Stage610 Entity Selector Tokens

Artifact: `runs/local/artifacts/stage610_entity_selector_tokens_summary.json`

## Result

Stage610 adds repeated entity+field selector markers to `entity_context` rows while preserving candidate keys.

Stage602 on Stage607 role-token exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Stage602 schema-only on Stage610 exact/answer: `0.8799145299145299` / `0.9051282051282051`.

Stage610 trained exact/answer: `0.8786324786324786` / `0.9034188034188034`.

Entity-context schema-only exact/answer: `0.5729166666666666` / `0.6423611111111112`.

Hard-filter schema-only exact/answer: `0.9995726495726496` / `0.9995726495726496`.

Hard-filter corrections: `299` -> `280`.

## Decision

`accepted_schema_selector_gain_training_rejected`

## Finding

Repeating entity+field selector markers is a strong schema-only KBPP lever: Stage602 on the Stage610 surface substantially improves global and entity_context exact/answer versus the Stage607 role-token surface and improves hard-filter corrections. A 150-step continuation does not improve the schema-only result, so the gain is from selector encoding rather than additional training.
