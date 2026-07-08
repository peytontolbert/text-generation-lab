# Stage9404 Second-Span Support Interference Audit

Passed: `True`

Stage9403 stayed safe but regressed generation quality.

- Heldout exact: `5/16 -> 0/16` compared with Stage9399.
- Degenerate repetition rows: `0 -> 6`.
- Eval/strict loss improved numerically, but generation quality got worse.

Decision: do not continue from the Stage9401 broad second-span support manifest.

Next: branch from Stage9397/9399 and add minimal residual phrase-disambiguation rows, starting with `expected assertion behavior` versus `current repair invariant`.

Decoder CE, runtime, Gemma, harness, source/body emission, and promotion remain closed.
