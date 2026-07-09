# Stage9617 Integrated Residual Phrase Denoise Manifest

Passed: `True`
Rows: `80`
Family counts: `{'full_suffix_ladder': 52, 'phrase_suffix_support': 28}`
Split counts: `{'train': 58, 'eval': 12, 'strict_eval': 10}`

This manifest tests whether Stage9615 phrase-level suffix support transfers back into full residual suffix repair.

Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Run Stage9618 contract-only preflight for integrated residual-plus-phrase denoise, then a tiny integration probe if it passes.
