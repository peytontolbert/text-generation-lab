# Stage9643 Balanced Positive Per-Head Observe Manifest

Passed: `True`
Rows: `84`
Splits: `{'train': 28, 'eval': 28, 'strict_eval': 28}`
Label by split: `{'train': {'boundary_match': {'True': 14, 'False': 14}, 'target_prefix_match': {'True': 14, 'False': 14}}, 'eval': {'boundary_match': {'True': 14, 'False': 14}, 'target_prefix_match': {'True': 14, 'False': 14}}, 'strict_eval': {'boundary_match': {'True': 14, 'False': 14}, 'target_prefix_match': {'True': 14, 'False': 14}}}`
Strongest single-feature baseline: `0.5833333333333334` via `generated_len_bucket->boundary_match`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9643 passes, run Stage9644 tiny target-100M per-head balanced-positive probe; keep decoder/denoise/runtime closed.
