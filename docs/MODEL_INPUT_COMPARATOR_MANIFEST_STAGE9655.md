# Stage9655 Model-Input Comparator Manifest

Passed: `True`
Rows: `12`
Splits: `{'train': 4, 'eval': 4, 'strict_eval': 4}`
Prefix baselines: `{'prefix->boundary_match': 0.5, 'prefix->target_prefix_match': 0.5}`
Model-input comparator baselines: `{'model_boundary_token_relation->boundary_match': 1.0, 'model_boundary_token_relation->target_prefix_match': 1.0}`

`model_input.boundary_token_relation` is consumed by `_row_text`; `encoder_text` and `state_features` are not.

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9655 passes, run Stage9656 model-input comparator micro target-100M probe.
