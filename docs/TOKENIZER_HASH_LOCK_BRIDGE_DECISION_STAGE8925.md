# Stage8925 Tokenizer Hash Lock Bridge Decision

Passed: `True`

This stage hash-locks the source export tokenizer files and recovered target config, then records the active tokenizer decision.

Decision: keep the recovered 1506-vocab target tokenizer active. The 8207-vocab source export tokenizer is reference-only. No bridge mapping is built here.

Source vocab: `8207`
Target vocab: `1506`
Vocab delta: `6701`

No tokenizer swap, embedding resize, embedding copy, lm-head copy, state-dict load, execution, or training is authorized.
