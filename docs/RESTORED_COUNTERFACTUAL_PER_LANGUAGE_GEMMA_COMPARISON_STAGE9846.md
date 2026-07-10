# Stage9846 Restored Counterfactual Per-Language Gemma Comparison

Passed: `True`
100M wins: `2`
Gemma wins: `1`
Ties: `5`
Eval macro delta (100M-Gemma): `0.04999999999999999`
Strict macro delta (100M-Gemma): `0.0`

This stage is the first same-surface multilingual comparison on the restored evidence-removed and contradictory-evidence packet using row-level outputs from both the 100M model and Gemma.

Next: Use this restored counterfactual comparison to decide whether the 100M win survives evidence removal and contradictory causal flips, then fold the result back into the anti-cheat review packet.
