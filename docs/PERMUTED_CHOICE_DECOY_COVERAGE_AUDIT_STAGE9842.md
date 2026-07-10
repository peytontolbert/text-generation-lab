# Stage9842 Permuted-Choice Decoy Coverage Audit

Passed: `True`
Validated languages: `4`
Paired roots: `20`
Built-in decoy languages: `4`
Missing ablation languages: `4`
Missing causal-flip languages: `4`

This stage scores the stronger packet's built-in decoy slice directly from the real 100M and Gemma outputs instead of pretending ablation and causal-flip evidence already exist.

Next: Use this direct decoy audit to update the stage9841 anti-cheat cards, then run fresh ablation and causal-flip executions on the same packet before making a stronger no-shortcuts claim.

