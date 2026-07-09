# Stage9657 Widened Model-Input Comparator Manifest

Passed: `True`
Rows: `48`
Splits: `{'train': 16, 'eval': 16, 'strict_eval': 16}`
Languages: `{'python': 12, 'rust': 12, 'c_cpp': 12, 'web_js_ts_html': 12}`
Prefix baselines: `{'prefix->boundary_match': 0.5, 'prefix->target_prefix_match': 0.5}`
Language baselines: `{'language_family->boundary_match': 0.5, 'language_family->target_prefix_match': 0.5}`
Comparator baselines: `{'model_boundary_token_relation->boundary_match': 1.0, 'model_boundary_token_relation->target_prefix_match': 1.0}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9657 passes, run Stage9658 widened model-input comparator target-100M probe.
