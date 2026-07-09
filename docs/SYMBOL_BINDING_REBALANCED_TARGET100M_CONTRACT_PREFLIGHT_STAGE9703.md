# Stage9703 Symbol-Binding Rebalanced Target-100M Contract Preflight

Stage9703 validates the target-100M command surface for the repaired symbol-binding manifest without executing the model.

## Result

- Passed: `True`
- Probe scale: `target_100m`
- Native ablation required: `True`
- Model execution attempted: `False`
- Split counts: `{'eval': 16, 'other': 0, 'strict_eval': 16, 'train': 32}`

## Next

If continuing execution, run Stage9704 target-100M symbol-binding structured probe from the Stage9703 candidate command; otherwise inspect the contract/audit artifacts first.
