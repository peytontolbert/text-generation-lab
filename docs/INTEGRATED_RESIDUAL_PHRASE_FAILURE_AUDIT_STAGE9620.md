# Stage9620 Integrated Residual-Phrase Failure Audit

Passed: `True`

Stage9619 is a safe but quality-failing run. Phase1 stayed solved, decoder CE stayed closed, and prefix injection worked, but the mixed residual-plus-phrase phase2 objective collapsed into repeated route fragments.

Key comparison:

- Stage9615 phrase-only contentful: `1.0`
- Stage9615 phrase-only target prefix: `0.8333333333333334`
- Stage9619 integrated contentful: `0.08333333333333333`
- Stage9619 integrated target prefix: `0.0`
- Stage9619 integrated prefix start: `1.0`
- Stage9619 artifact counts: `{'match match': 4, 'unterminated': 11, 'degenerate_repetition': 11, 'match ins': 7, 'whitelist': 2}`

Diagnosis: one-pass full-suffix plus phrase-support training creates curriculum interference. Phrase support should be staged as an in-memory warm-up or intermediate phase before full residual suffix reconnect.

Authority remains closed: no decoder CE reopen, no runtime, no Gemma, no harness, no checkpoint export, no promotion.

Next: Design Stage9621 tri-phase in-memory residual reconnect wrapper: suffix-choice sidecar, phrase-suffix warm-up, then full residual suffix ladder; run contract-only preflight before execution.
