# Stage9248 Bounded Decoder Target Semantic Diversity Audit

Passed: `False`

Rows: `64`
First-token dominance rate: `1.000`
Language-prefix rows: `64`
Target contains language rows: `64`
Argument-type echo rows: `64`
Template phrase rows: `64`
Unique normalized target rate: `0.469`
Unique trigram rate: `0.064`

This is a no-execution audit. It does not train or instantiate the model. It checks whether the current bounded decoder targets are meaningful enough for capability interpretation rather than template memorization.

Decision: Stage9244 target text is too templated or label-echoed for capability interpretation; do not execute the tiny CE probe until target rendering is repaired.
Next: Repair the bounded decoder target renderer to produce non-template, non-label-echo, source-backed bounded argument targets, then rerun package/preflight/review.

