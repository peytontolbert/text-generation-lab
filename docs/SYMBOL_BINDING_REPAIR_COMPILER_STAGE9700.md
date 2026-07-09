# Stage9700 Symbol-Binding Repair Compiler

Stage9700 recompiles the source-backed symbol-binding tiny manifest after Stage9699 diagnosed split coverage gaps and call-label collapse.

## Repair

- Preserves all 64 row IDs.
- Reassigns splits to keep the 32/16/16 cap.
- Ensures every binding label appears in train, eval, and strict_eval.
- Leaves decoder CE, runtime, Gemma, harness, and promotion closed.

## Result

- Passed: `True`
- Moved rows: `39`
- Split sizes: `{'eval': 16, 'strict_eval': 16, 'train': 32}`
- Missing labels by split: `{'train': [], 'eval': [], 'strict_eval': []}`

## Next

Run Stage9701 contract-only preflight on the Stage9700 rebalanced symbol-binding manifest, including single-feature shortcut baselines and a native grouped-ablation telemetry design; do not execute target-100M yet.
