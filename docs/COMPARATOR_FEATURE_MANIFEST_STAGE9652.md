# Stage9652 Comparator Feature Manifest

Passed: `True`
Rows: `12`
Splits: `{'train': 4, 'eval': 4, 'strict_eval': 4}`
Prefix baselines: `{'prefix->boundary_match': 0.5, 'prefix->target_prefix_match': 0.5}`
Comparator baselines: `{'boundary_token_relation->boundary_match': 1.0, 'boundary_token_relation->target_prefix_match': 1.0}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9652 passes, run Stage9653 comparator-feature micro target-100M probe.
