# Stage9831 Same-Surface Counterfactual Gemma Comparison

Passed: `True`
Rows compared: `40`
100M wins: `6`
Gemma wins: `1`
Ties: `1`
Eval macro delta (100M-Gemma): `0.2`
Strict macro delta (100M-Gemma): `0.15000000000000002`
Shortcut-risk winning cells: `4`

This stage compares Gemma-12B and the current 100M execution on the exact same counterfactual surface rather than mixing old frontier rows with newer robustness probes.

Next: Use this same-surface counterfactual comparison to decide whether the multilingual winner is actually robust enough to headline; if Gemma holds up on mixed-replay, improve the training/data surface before making stronger public win claims.

