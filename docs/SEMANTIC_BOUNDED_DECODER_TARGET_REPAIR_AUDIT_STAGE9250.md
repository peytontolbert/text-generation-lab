# Stage9250 Semantic Bounded Decoder Target Repair Audit

Passed: `True`

Rows: `64`
First-token dominance rate: `0.281`
Language-prefix rows: `0`
Target contains language rows: `0`
Argument-type echo rows: `0`
Template phrase rows: `0`
Unique normalized target rate: `1.000`
Unique trigram rate: `0.241`

This audit is no-execution. It verifies that Stage9249 repaired the Stage9248 target-rendering blocker without opening model execution, decoder training, runtime, Gemma, harness, scoring, or promotion.

Next: Run target-100M contract-only preflight on the Stage9249 repaired manifest, then create a fresh inactive execution review if it passes.

