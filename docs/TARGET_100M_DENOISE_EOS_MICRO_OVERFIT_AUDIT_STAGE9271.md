# Stage9271 Target-100M Denoise EOS Micro-Overfit Audit

EOS weighting and 80 steps improved generation, but did not recover semantic targets.

Contentful rate: 0.0 -> 0.6923076923076923
Unterminated rate: 1.0 -> 0.3076923076923077
Degenerate repetition rate: 0.3076923076923077 -> 0.23076923076923078
Target prefix match rate: 0.0
Train loss: 81.18218994140625 -> 0.1625075340270996

Next step is target-grounded denoise data, not data widening.
