# Stage9276 Prefix-Primed Denoise Probe Audit

Decoder prefix priming now works, but continuation semantics still fail.

Generation prefix start rate: 1.0
Contentful rate: 0.38461538461538464 -> 0.38461538461538464
Unterminated rate: 0.6153846153846154 -> 0.6153846153846154
Degenerate repetition rate: 0.5384615384615384 -> 0.46153846153846156
Target prefix match rate: 0.0
Diagnosis: decoder_start_control_fixed_continuation_semantics_still_failing

Next step: continuation-bridge objective for the first post-prefix span and EOS boundary.
