# Stage10048 Python Symbol Test Target100M Execution Request

Passed: `True`
Rows: `103`
Heldout compare rows: `55`

Materialized the target-100M execution request for the Python symbol-vs-test source-backed successor manifest so the next run can test a fresh-data fix rather than replaying heldout rows.

This stage is request-only. It does not authorize or execute the model run.

Next: Use this request to run one target-100M edit-localization probe on the stage10047 Python successor manifest, then compare the resulting heldout rows directly against the existing same-manifest Gemma outputs.
