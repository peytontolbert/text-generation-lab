# Stage10002 Duplicate RowID Eval Audit

Passed: `True`
Duplicate heldout row IDs: `1`

Audited the source-heldout manifest for duplicate heldout row IDs and found an exact c_cpp duplicate that should be removed from future reruns.

Next: Deduplicate the source-heldout manifest by row_id before future training or comparison reruns so heldout row counts and shared-row counts match exactly.
