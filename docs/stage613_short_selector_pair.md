# Stage613 Short Selector Pair

Artifact: `runs/local/artifacts/stage613_short_selector_pair_summary.json`

## Result

Stage607 role-token exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Previous selector exact/answer: `0.9004273504273504` / `0.9209401709401709`.

Candidate exact/answer: `0.9042735042735043` / `0.9247863247863248`.

Entity-context exact/answer: `0.7708333333333334` / `0.8020833333333334`.

Average train retrieval tokens per pair: `141.92402780221713`.

Hard-filter corrections: `223`.

## Decision

`accepted_short_selector_pair_schema_best`

## Finding

Shortening selector_pair to sp preserves and slightly improves the Stage612 gain while reducing token cost. The model does not need a semantic selector key name; it benefits from a compact pair anchor.
