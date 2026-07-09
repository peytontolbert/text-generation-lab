# Stage9687 Locked Eval Train Exclusion Guard

Passed: `True`
Fixture rows: `4`
Locked source IDs loaded: `72`
Locked exclusion rows: `3`
Decoder CE rows after guard: `1`
Blocked rows with forbidden loss: `[]`

The negative fixture proves direct locked source IDs, nested source lineage IDs, and locked split roles are forced to human review before loss masks can authorize training.

No Gemma, harness, runtime, model execution, scoring, source/body emission, training, checkpoint export, or promotion is authorized.

Next: Build Stage9688 locked-eval guard graph attachment and then resume non-eval training package selection with locked-source exclusions required.
