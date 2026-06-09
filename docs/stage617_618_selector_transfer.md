# Stage617-618 Selector Transfer

Artifacts:

- `runs/local/artifacts/stage617_direct_fact_selector_transfer.json`
- `runs/local/artifacts/stage618_entity_direct_selector_transfer.json`

## Result

Stage617 applied `{entity}:{field}` to `direct_fact` only.

- Exact/answer: `0.8918803418803419` / `0.9085470085470085`
- Direct_fact exact/answer: `0.8927444794952681` / `0.8958990536277602`
- Average train retrieval tokens per pair: `135.09189688544782`
- Hard-filter corrections: `240`

Stage618 applied `{entity}:{field}` to both `entity_context` and `direct_fact`.

- Exact/answer: `0.9358974358974359` / `0.9508547008547008`
- Exact/answer bits per param: `1.5055971292193477` / `1.5296591837959126`
- Entity_context exact/answer: `0.8645833333333334` / `0.875`
- Direct_fact exact/answer: `0.8927444794952681` / `0.8958990536277602`
- Average train retrieval tokens per pair: `136.49115783916946`
- Hard-filter exact/answer: `1.0` / `1.0`
- Hard-filter corrections: `150`

## Decision

`accepted_entity_direct_selector_transfer_best`

## Finding

Minimal colon selectors transfer cleanly to `direct_fact`, and combining `entity_context` plus `direct_fact` is strongly positive. This is the first selector transfer that raises the field-surface answer bits/param above `1.52` while keeping token cost modest.
