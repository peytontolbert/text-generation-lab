# Stage9479 Episode Target-Prefix Balance Manifest

Passed: `True`
Rows: `50`
Splits: `{'train': 46, 'eval': 2, 'strict_eval': 2}`
Split label counts: `{'train': {'true': 19, 'false': 27}, 'eval': {'true': 1, 'false': 1}, 'strict_eval': {'false': 1, 'true': 1}}`
Enabled loss: `episode_target_prefix_match_ce`

This manifest isolates the Stage9478 residual target-prefix field. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
