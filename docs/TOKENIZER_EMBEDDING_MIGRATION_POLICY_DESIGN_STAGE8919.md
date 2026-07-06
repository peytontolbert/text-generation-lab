# Stage8919 Tokenizer Embedding Migration Policy Design

Passed: `True`

This stage records the metadata-only policy for the 8207-to-1506 tokenizer/vocab mismatch.

Default policy: keep the recovered target tokenizer at vocab 1506 and do not load/copy source export embeddings or lm_head rows.

Blocked until future authorization: tokenizer swap, embedding resize, lm_head resize/copy, new token row initialization, state-dict load, checkpoint write, execution, and training.

Source vocab: `8207`
Recovered target vocab: `1506`
Vocab delta: `6701`
