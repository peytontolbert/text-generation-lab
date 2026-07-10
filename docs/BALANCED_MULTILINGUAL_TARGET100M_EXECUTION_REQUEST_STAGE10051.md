# Stage10051 Balanced Multilingual Target100M Execution Request

Passed: `True`
Rows: `121`
Heldout compare rows: `55`

Materialized the target-100M execution request for the balanced multilingual successor manifest so the next run can test whether the Python fix can be retained without losing multilingual strength.

This stage is request-only. It does not authorize or execute the model run.

Next: Use this request to run one target-100m edit-localization probe on the balanced multilingual successor manifest, then compare the heldout rows directly against Gemma and the stage10048 successor run.
