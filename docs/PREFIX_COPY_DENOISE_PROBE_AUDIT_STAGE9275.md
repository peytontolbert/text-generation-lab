# Stage9275 Prefix-Copy Denoise Probe Audit

Safety passed, but visible prefix-copy input did not recover generation starts.

Contentful rate: 0.46153846153846156 -> 0.38461538461538464
Unterminated rate: 0.5384615384615384 -> 0.6153846153846154
Degenerate repetition rate: 0.15384615384615385 -> 0.5384615384615384
Target prefix match rate: 0.0
Anchor prefix start rate: 0.0
Anchor prefix contains rate: 0.0
Diagnosis: visible_prefix_input_not_used_by_free_generation

Next step: audited decoder-prefix priming from approved prefix spans.
