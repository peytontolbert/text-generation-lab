# Stage9278 Continuation-Bridge Denoise Probe Audit

Stage9278 improved stability but did not recover the continuation bridge.

Generation prefix start rate: 1.0
Bridge start rate: 0.0
Contentful rate: 0.38461538461538464 -> 0.6153846153846154
Unterminated rate: 0.6153846153846154 -> 0.38461538461538464
Degenerate repetition rate: 0.46153846153846156 -> 0.23076923076923078
Target prefix match rate: 0.0
Diagnosis: continuation_bridge_improves_stability_but_bridge_copy_still_fails

Next step: decoder-side bridge priming or shorter next-token bridge objective.
