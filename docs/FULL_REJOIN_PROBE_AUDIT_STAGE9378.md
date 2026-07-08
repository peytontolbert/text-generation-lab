# Stage9378 Full Rejoin Probe Audit

Passed: `True`
Safety gate passed: `True`
Quality gate passed: `True`
Exact match rows: `276` / `276`
Target-prefix rows: `276` / `276`
Boundary next-token rows: `276` / `276`
Contentful rows: `276` / `276`
Short/junk rows: `0`
Repetition rows: `0`
Leak rows: `0`
Eval loss: `2.4937335751928913e-07`
Strict eval loss: `4.902584578303504e-07`

This resolves the Stage9366 mixed repair quality blocker. Decoder CE, runtime, Gemma, harness, scoring, source/body emission, promotion, and controller merge remain closed.
