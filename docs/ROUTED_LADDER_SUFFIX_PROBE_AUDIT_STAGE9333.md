# Stage9333 Routed Ladder Suffix Probe Audit

Passed: `False`
Safety gate passed: `True`
Quality gate passed: `False`
Exact match rows: `35` / `56`
Target prefix match rate: `0.625`
Boundary next-token match rate: `0.875`
Contentful generation rate: `0.8571428571428571`
Degenerate repetition rows: `8`
Error counts: `{'keeps_the_repetition': 7, 'verified_inserted_before_preserves': 6, 'operatch_repetition': 8, 'extra_verified_before_preserves': 6, 'boundary_whitespace_over_expected': 7, 'other': 0}`

The safety contract held: decoder CE, runtime, Gemma, harness, scoring, and checkpoint export stayed closed.
The quality contract failed after merging routed phrase rows back with the ladder. Residual failures are concentrated in `keeps the` repetition, `verified preserves` insertion, and `operatch` repetition.
Next patch should be targeted anti-insertion/repetition rows, not a generic wider probe.
