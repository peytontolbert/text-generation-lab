# Stage615 Raw Selector No Role Tokens

Artifact: `runs/local/artifacts/stage615_raw_selector_no_role_tokens_summary.json`

## Result

Stage615 uses the Stage602 field-level balanced dataset, adds raw `entity|field`, and removes Stage607 `FIELD_ROLE_*` tokens.

Original Stage602 field surface exact/answer: `0.8722222222222222` / `0.8914529914529915`.

Stage607 role-token surface exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Stage614 raw selector with role tokens exact/answer: `0.9064102564102564` / `0.9260683760683761`.

Stage615 raw selector without role tokens exact/answer: `0.9111111111111111` / `0.9286324786324787`.

Entity-context exact/answer: `0.8229166666666666` / `0.8333333333333334`.

Average train retrieval tokens per pair: `133.72835650184763`.

Hard-filter corrections: `207`.

## Decision

`accepted_minimal_raw_selector_best`

## Finding

FIELD_ROLE tokens are not needed once the raw entity|field selector is present. Stage615 improves over Stage614, improves over the original Stage602 field surface, and cuts retrieval token cost. The minimal selector pair is now the strongest entity-context KBPP lever.
