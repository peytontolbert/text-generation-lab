# Stage9885 Current Margin Hybrid Counterfactual Execution Manifest

Passed: `True`
Rows: `48`
Split counts: `{'eval': 16, 'strict_eval': 16, 'train': 16}`
Kept obligations: `{'MIXED_REPLAY': 8, 'POSITIVE_ORIGINAL': 16, 'POSITIVE_ORIGINAL_EVAL_REPLAY': 16, 'POSITIVE_ORIGINAL_STRICT_ANCHOR': 8}`
Strict label balance: `{'K': 4, 'M': 4, 'R': 4, 'T': 4}`

This stage preserves current-frontier multilingual label balance while reducing strict-set collapse pressure on the weakest labels.

Next: Run one target-100M probe on this hybrid manifest to test whether clean strict anchors for K and T preserve frontier strict exact while still exposing mixed-replay pressure on M and R.

