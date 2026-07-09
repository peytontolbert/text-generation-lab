# Stage9656 Model-Input Comparator Tiny Probe

Passed: `True`
Safety passed: `True`
Quality passed: `True`
Eval/strict joint: `1.0` / `1.0`
Eval field exact: `{'episode_boundary_match': 1.0, 'episode_target_prefix_match': 1.0}`
Strict field exact: `{'episode_boundary_match': 1.0, 'episode_target_prefix_match': 1.0}`
Wrong by field: `{}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9656 passes, widen model-input comparator rows; if it fails, inspect tokenization/row_text rendering for model_input fields.
