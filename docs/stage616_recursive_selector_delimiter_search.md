# Stage616 Recursive Selector Delimiter Search

Artifact: `runs/local/artifacts/stage616_recursive_selector_delimiter_search.json`

## Result

The recursive KBPP selector hill-climb evaluated six compact entity selector templates on the Stage602 field-level surface.

Best candidate: `{entity}:{field}`.

- Exact/answer: `0.9162393162393162` / `0.9337606837606838`
- Exact/answer bits per param: `1.473972714633005` / `1.5021596928512668`
- Average train retrieval tokens per pair: `133.72835650184763`
- Hard-filter corrections: `195`

Ranking by answer bits/param:

1. `{entity}:{field}`
2. `{entity}/{field}`
3. `{entity}-{field}`
4. `{entity}|{field}`
5. `{entity}_{field}`
6. `{field}|{entity}`

## Decision

`accepted_recursive_selector_delimiter_best`

## Finding

The delimiter and order matter. Entity-first is required, and `:` is the best tested delimiter. The current best selector rule is minimal entity-first pair identity with colon delimiter: `entity:field`.
