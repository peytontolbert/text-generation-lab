# Stage9829 Current Winner Counterfactual Execution Manifest

Passed: `True`
Rows: `60`
Split counts: `{'eval': 20, 'strict_eval': 20, 'train': 20}`
Kept obligations: `{'MIXED_REPLAY': 20, 'POSITIVE_ORIGINAL': 20, 'POSITIVE_ORIGINAL_EVAL_REPLAY': 20}`
Dropped obligations: `{'CONTRADICTORY_EVIDENCE_OR_UNSAFE_TWIN': 20, 'EVIDENCE_REMOVED': 20}`

This stage makes the stronger counterfactual bank executable under the recovered trainer without losing multilingual label coverage in any split bucket.

Next: Run a real target-100M structured probe on the stage9829 execution manifest, then replay the full stage9828 evidence-removed and contradictory counterfactual bank as a frozen-model audit instead of trying to train through a non-separable surface.

