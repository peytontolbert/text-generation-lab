# Stage614 Raw Selector Pair

Artifact: `runs/local/artifacts/stage614_raw_selector_pair_summary.json`

## Result

Stage607 role-token exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Previous selector exact/answer: `0.9042735042735043` / `0.9247863247863248`.

Candidate exact/answer: `0.9064102564102564` / `0.9260683760683761`.

Entity-context exact/answer: `0.7881944444444444` / `0.8125`.

Average train retrieval tokens per pair: `141.32434453633644`.

Hard-filter corrections: `218`.

## Decision

`accepted_raw_selector_pair_schema_best`

## Finding

Removing the selector key entirely and inserting the raw entity|field pair gives the best selector surface so far. The useful bit is the pair identity itself, and every extra key-name token has been overhead.
