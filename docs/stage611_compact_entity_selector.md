# Stage611 Compact Entity Selector

Artifact: `runs/local/artifacts/stage611_compact_entity_selector_summary.json`

## Result

Stage611 compresses Stage610's entity selector to one `selector_pair=entity|field` marker.

Stage602 on Stage607 role-token exact/answer: `0.8692307692307693` / `0.8957264957264958`.

Stage610 full-selector exact/answer: `0.8799145299145299` / `0.9051282051282051`.

Stage611 compact-selector exact/answer: `0.888034188034188` / `0.9098290598290598`.

Entity-context exact/answer: `0.6388888888888888` / `0.6805555555555556`.

Average train retrieval tokens per pair: Stage610 `147.88329227520677` -> Stage611 `144.32276086573992`.

Hard-filter corrections: Stage610 `280` -> Stage611 `261`.

## Decision

`accepted_compact_selector_schema_best`

## Finding

A compact entity-field pair selector outperforms the longer Stage610 selector and uses fewer retrieval tokens. This means selector identity weighting, not verbose repeated domain/entity/field spelling, carries the entity-context gain.
