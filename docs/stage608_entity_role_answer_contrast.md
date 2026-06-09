# Stage608 Entity Role Answer Contrast

Artifact: `runs/local/artifacts/stage608_entity_role_answer_contrast_summary.json`

## Result

Stage608 trained on the Stage607 role-token schema with entity-context answer contrast.

Stage602 role-token baseline exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Stage608 exact/answer: `0.867948717948718` / `0.8935897435897436`.

Hard-filter corrections: `299` -> `302`.

Entity-context exact/answer: `0.4861111111111111` / `0.5625`.

## Decision

`rejected_answer_contrast_on_role_tokens`

## Finding

Entity answer contrast on the role-token schema moves in the wrong direction: exact, answer, entity_context, direct_fact, and rule intersections all fall versus the Stage602 schema baseline, while hard-filter corrections increase. The answer-directed path should not use the existing broad answer-contrast loss on entity_context.
