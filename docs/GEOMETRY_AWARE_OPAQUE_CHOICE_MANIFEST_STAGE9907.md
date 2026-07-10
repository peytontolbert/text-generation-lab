# Stage9907 Geometry-Aware Opaque Choice Manifest

Passed: `True`
Rows: `48`
Split counts: `{'eval': 16, 'strict_eval': 16, 'train': 16}`

Built a geometry-aware opaque-choice manifest from the current Stage9893 packet, permuting the local option-to-semantic mapping independently per row so same-surface evaluation no longer relies on a globally exposed label identity.

Next: Run a fresh target-100M probe and same-surface Gemma comparison on this opaque-choice geometry-aware packet without exposing the global valid-label list in the prompt.
