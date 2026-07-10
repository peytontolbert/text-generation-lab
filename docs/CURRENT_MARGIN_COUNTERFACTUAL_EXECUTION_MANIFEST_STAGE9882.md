# Stage9882 Current Margin Counterfactual Execution Manifest

Passed: `True`
Rows: `48`
Split counts: `{'eval': 16, 'strict_eval': 16, 'train': 16}`
Kept obligations: `{'MIXED_REPLAY': 16, 'POSITIVE_ORIGINAL': 16, 'POSITIVE_ORIGINAL_EVAL_REPLAY': 16}`
Dropped obligations: `{'CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN': 16, 'EVIDENCE_REMOVED': 16}`

This stage makes the current-frontier stronger counterfactual bank executable under the recovered trainer without losing multilingual label coverage in any split bucket.

Next: Run one target-100M structured probe on the Stage9882 execution manifest, then replay the full Stage9881 evidence-removed and contradictory bank as a frozen-model audit to measure whether the current frontier survives stronger shortcut probes.

