# Stage9649 Same-Prefix Contrast Manifest

Passed: `True`
Rows: `12`
Splits: `{'train': 4, 'eval': 4, 'strict_eval': 4}`
Label by split: `{'train': {'boundary_match': {'True': 2, 'False': 2}, 'target_prefix_match': {'True': 2, 'False': 2}}, 'eval': {'boundary_match': {'True': 2, 'False': 2}, 'target_prefix_match': {'True': 2, 'False': 2}}, 'strict_eval': {'boundary_match': {'True': 2, 'False': 2}, 'target_prefix_match': {'True': 2, 'False': 2}}}`
Prefix baselines: `{'prefix->boundary_match': 0.5, 'prefix->target_prefix_match': 0.5}`
Semantic evidence baselines: `{'boundary_token_pair->boundary_match': 1.0, 'boundary_token_pair->target_prefix_match': 1.0}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9649 passes, run Stage9650 same-prefix micro-overfit target-100M probe.
