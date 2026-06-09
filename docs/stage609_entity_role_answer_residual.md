# Stage609 Entity Role Answer Residual

Artifact: `runs/local/artifacts/stage609_entity_role_answer_residual_summary.json`

## Result

Stage609 trained a narrow residual continuation on the Stage607 role-token schema, using only entity-context answer misses and weak answer contrast.

Stage602 role-token baseline exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Stage609 exact/answer: `0.8683760683760684` / `0.8952991452991453`.

Hard-filter corrections: `299` -> `301`.

Entity-context exact/answer: `0.4826388888888889` / `0.5659722222222222`.

## Decision

`rejected_narrow_answer_residual_on_role_tokens`

## Finding

Narrowing Stage608 to role-token entity answer misses avoids the entity-context answer drop, but it still lowers global exact/answer, lowers direct_fact and set_intersection_member exact, and raises hard-filter corrections. The remaining entity-context KBPP gain needs a selector/schema change, not weaker answer-contrast tuning.
