# Stage10085 Canonical Label Aligned Source-Heldout Same Manifest Gemma Queue

Passed: `True`
Heldout rows: `55`

Materialized a same-manifest Gemma queue for the canonical source-heldout multilingual rows so Gemma can be compared fairly on the honest heldout bank after label-semantic alignment.

Next: Run the local Ollama Gemma comparator on this canonical source-heldout same-manifest queue, then compare it directly against the matching 100M probe on the same 55 heldout rows.
