# Stage10071 Canonical Label Aligned Same Manifest Gemma Queue

Passed: `True`
Heldout rows: `55`

Materialized a same-manifest Gemma queue for the canonical-label multilingual heldout rows so Gemma can be compared fairly on the remapped label semantics.

Next: Run the local Ollama Gemma comparator on this canonical-label same-manifest queue, then compare it directly against the matching 100M probe on the same 55 heldout rows.
