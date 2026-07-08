# Stage9280 Bridge-Primed Denoise Probe Audit

Stage9280 forced a longer 8-word target-start span and regressed suffix generation quality.

Generation prefix start rate: 1.0
Contentful rate: 0.6153846153846154 -> 0.38461538461538464
Unterminated rate: 0.38461538461538464 -> 0.6153846153846154
Degenerate repetition rate: 0.23076923076923078 -> 0.46153846153846156
Target prefix match rate: 0.0
Diagnosis: longer_decoder_priming_regressed_suffix_generation

Next step: inspect token loss around the first unforced suffix token; build suffix micro-overfit rows.
