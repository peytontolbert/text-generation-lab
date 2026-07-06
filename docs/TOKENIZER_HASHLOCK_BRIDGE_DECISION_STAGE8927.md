# Stage8927 Tokenizer Hash-Lock Bridge Decision

Passed: `True`

This no-execution stage locks tokenizer file hashes and records a bridge-token decision for the 8207-to-1506 mismatch.

Current decision: keep recovered target tokenizer at vocab 1506. Source tokenizer swap, embedding resize/copy, lm_head resize/copy, token row initialization, state-dict load, checkpoint write, model execution, and training remain blocked.
