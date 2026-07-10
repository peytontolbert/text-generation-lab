# Stage9835 Permuted Choice Gemma Comparison

Passed: `True`
Rows compared: `40`
100M wins: `2`
Gemma wins: `0`
Ties: `0`
Eval macro delta (100M-Gemma): `0.3`
Strict macro delta (100M-Gemma): `0.10000000000000003`

This stage tests the 100M-versus-Gemma claim on a same-surface packet where the option-to-semantic mapping is permuted per row rather than globally stable. The 100M side currently has split-level exactness only because the runtime did not emit row-level per-language records for Stage9834.

Next: If the 100M win survives the permuted-choice surface, use this as the default same-surface comparison packet for future multilingual claims and only promote after the blind expert-maintainer review is filled in.

