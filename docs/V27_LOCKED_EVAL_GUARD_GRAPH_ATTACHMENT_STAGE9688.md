# Stage9688 Locked Eval Guard Graph Attachment

Passed: `True`
Graph nodes: `1820`
Graph edges: `2729`
Locked exclusion rows in fixture: `3`
Decoder CE rows after guard: `1`

The central graph now records locked eval exclusion as a hard compiler control that runs before loss-mask creation.

No Gemma, harness, runtime, model execution, scoring, source/body emission, training, checkpoint export, or promotion is authorized.

Next: Resume non-eval training package selection with --locked-source-exclusions required, then run contract-only target_100m preflight under the locked-source guard.
