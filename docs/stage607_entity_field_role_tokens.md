# Stage607 Entity Field Role Tokens

Artifact: `runs/local/artifacts/stage607_entity_field_role_tokens_summary.json`

## Result

Stage607 adds explicit `FIELD_ROLE_*` tokens to `entity_context` field rows.

Stage602 on the original Stage601 surface: exact/answer `0.8722222222222222` / `0.8914529914529915`.

Stage602 on the Stage607 role-token surface: exact/answer `0.8692307692307693` / `0.8957264957264958`.

Stage607 trained checkpoint: exact/answer `0.8692307692307693` / `0.8952991452991453`.

Hard-filter exact/answer on the role-token surface: `0.997008547008547` / `0.997008547008547`.

Entity-context trained exact/answer: `0.4895833333333333` / `0.5659722222222222`.

## Decision

`accepted_as_schema_answer_gain_training_not_frontier`

## Finding

Explicit field-role tokens validate the Stage606 diagnosis: the schema alone raises answer accuracy and hard-filter ceiling on entity_context, but it lowers exact-card identity. Training on the role-token surface recovers a little entity exactness but gives back answer accuracy and does not improve the hard-filter result. Treat role tokens as a schema lever for answer reliability, not yet a pure-neural exact frontier.
