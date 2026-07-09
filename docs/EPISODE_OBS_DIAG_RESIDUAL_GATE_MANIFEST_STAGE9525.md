# Stage9525 Episode Observation Diagnosis Residual-Gate Manifest

Passed: `True`
Rows: `58`
Split counts: `{'train': 46, 'eval': 6, 'strict_eval': 6}`
Alignment counts: `{'prefix_residual_observation': 16, 'clean_success_observation': 29, 'boundary_residual_observation': 13}`
Stage9524 wrong source counts: `{'False': 56, 'True': 2}`

This patch keeps minimal context but adds observation-derived residual gates and removes the stale eval-only repair-focus marker from model input.
