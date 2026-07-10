# Stage9884 Current Margin Counterfactual Probe Audit

Passed: `True`
Eval exact: `0.4375`
Strict exact: `0.5`
Delta vs broader eval: `0.0`
Delta vs broader strict: `-0.0625`
Dominant confusions: `{'K': 'R', 'M': 'M', 'R': 'R', 'T': 'T'}`

The Stage9882 current-frontier mixed-replay rerun is executable and contract-clean, but it does not improve the frontier: eval exact matches the broader baseline while strict exact regresses.

Next: Do not promote the Stage9882 mixed-replay path directly. Either rebalance the strict mixed-replay labels or keep Stage9881 as a frozen audit bank while optimizing the main Stage9867/9878 training path separately.

