# Stage9658 Widened Model-Input Comparator Tiny Probe

Passed: `True`
Safety passed: `True`
Quality passed: `True`
Eval/strict joint: `1.0` / `1.0`
Eval field exact: `{'episode_boundary_match': 1.0, 'episode_target_prefix_match': 1.0}`
Strict field exact: `{'episode_boundary_match': 1.0, 'episode_target_prefix_match': 1.0}`
Wrong by field: `{}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9658 passes, reintegrate comparator-visible model_input features into the broader observe/repair episode manifest; if it fails, inspect per-language field errors.
