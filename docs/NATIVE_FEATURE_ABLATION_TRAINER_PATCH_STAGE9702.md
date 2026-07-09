# Stage9702 Native Feature-Ablation Trainer Patch

Stage9702 patches the structured trainer so `--require-native-feature-ablation-audit` emits native grouped mask-rerun attribution rows instead of deterministic proxy rows.

## Result

- Passed: `True`
- Native ablation rows: `32`
- Ablation modes: `['native_grouped_mask_rerun']`
- Full target-100M authorized in smoke: `False`
- Decoder delta norm: `0.0`

## Next

Run Stage9703 target-100M contract-only preflight on the Stage9700 repaired manifest with --require-native-feature-ablation-audit; do not execute until that preflight passes.
