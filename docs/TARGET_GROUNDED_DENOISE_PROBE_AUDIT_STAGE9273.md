# Stage9273 Target-Grounded Denoise Probe Audit

Safety passed, but target-grounded anchors did not recover target prefixes.

Contentful rate: 0.6923076923076923 -> 0.46153846153846156
Unterminated rate: 0.3076923076923077 -> 0.5384615384615384
Degenerate repetition rate: 0.23076923076923078 -> 0.15384615384615385
Target prefix match rate: 0.0
Diagnosis: minimal_target_anchors_too_weak_for_prefix_recovery

Next step: prefix-copy micro-objective with leak-safe short prefixes.
