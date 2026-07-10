# Stage9849 Counterfactual Curriculum Gemma Comparison

Passed: `True`
100M wins: `0`
Gemma wins: `3`
Ties: `5`
Eval macro delta (100M-Gemma): `-0.25`
Strict macro delta (100M-Gemma): `-0.25`

This stage measures whether explicit curriculum training on missing-evidence and contradictory-evidence behaviors creates a stronger heldout multilingual comparison against Gemma.

Next: If this curriculum improves the harder multilingual comparison, fold it back into the anti-cheat review packet and consider scaling the same objective into the main v2.7 training path.
