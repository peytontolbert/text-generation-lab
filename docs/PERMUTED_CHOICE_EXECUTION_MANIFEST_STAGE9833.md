# Stage9833 Permuted Choice Execution Manifest

Passed: `True`
Rows: `60`
Split counts: `{'eval': 20, 'strict_eval': 20, 'train': 20}`

This stage keeps the same multilingual edit-localization counterfactual packet but destroys any stable global A-E semantic mapping by permuting choice semantics independently inside each bucket.

Next: Run a fresh target-100M structured probe and same-surface Gemma comparison on the permuted-choice manifest so fixed A-E semantic shortcuts are no longer stable across rows.
