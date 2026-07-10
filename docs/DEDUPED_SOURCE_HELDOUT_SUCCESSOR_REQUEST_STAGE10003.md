# Stage10003 Deduped Source-Heldout Successor Request

Passed: `True`
Rows kept: `77`
Removed duplicate eval rows: `1`

Materialized a deduplicated source-heldout successor manifest that removes the single duplicate heldout row ID from stage9997.

Next: Use this deduplicated source-heldout manifest for future reruns so heldout row counts, unique row IDs, and comparison coverage all match without implicit collapsing.
