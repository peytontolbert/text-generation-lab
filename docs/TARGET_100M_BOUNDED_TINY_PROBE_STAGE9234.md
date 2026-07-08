# Stage9234 Target 100M Bounded Tiny Probe

Passed: `True`

This stage executed the recovered 102M AgentKernel Lite transformer on the real bounded decoder tiny-cap manifest under `trellis`.

Scope:
- bounded decoder CE only
- 32/16/16 train/eval/strict rows
- 16 optimizer steps
- repo-local 1506-token tokenizer
- no runtime/Gemma/harness/scoring
- no checkpoint export

Key metrics:
- parameter count: `102668531`
- train loss first/last step: `84.9995346069336` -> `7.893095970153809`
- eval loss: `13.711634635925293`
- strict eval loss: `18.407922744750977`
- row token loss rows: `32`
- internal target rows: `0`
- internal token probability mass: `0.0`
- decoder delta norm: `2.112376482098783`
- encoder delta norm: `1.1197748889536356`
- structured head delta norm: `0.0`

Boundary:
Sampling/generation remained disabled. This is not a contentful-output or codegen proof yet.

Next: Audit why eval/strict losses remain high and target repetition is present in all eval rows; then run a second tiny probe only after adding either same-row before/after loss telemetry or a generation-enabled audit wrapper. Do not widen data yet.
