# Stage612 Bare Selector Pair

Artifact: `runs/local/artifacts/stage612_bare_selector_pair_summary.json`

## Result

Stage612 removes the explicit `ENTITY_SELECTOR` label and keeps only `selector_pair=entity|field`.

Stage607 role-token exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Stage611 compact selector exact/answer: `0.888034188034188` / `0.9098290598290598`.

Stage612 bare selector exact/answer: `0.9004273504273504` / `0.9209401709401709`.

Entity-context exact/answer: `0.7430555555555556` / `0.7708333333333334`.

Average train retrieval tokens per pair: Stage611 `144.32276086573992` -> Stage612 `143.12339433397852`.

Hard-filter corrections: Stage611 `261` -> Stage612 `232`.

## Decision

`accepted_bare_selector_pair_schema_best`

## Finding

The explicit ENTITY_SELECTOR label is unnecessary and harmful. A bare selector_pair=entity|field marker is shorter and substantially stronger, lifting entity_context exact/answer while reducing hard-filter corrections.
