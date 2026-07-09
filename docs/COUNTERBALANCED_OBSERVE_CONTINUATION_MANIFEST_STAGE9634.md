# Stage9634 Counterbalanced Observe Continuation Manifest

Passed: `True`
Rows: `48`
Splits: `{'train': 16, 'eval': 16, 'strict_eval': 16}`
Strongest single-feature baseline: `0.6875` via `generated_len_bucket->boundary_match`
Counterpositive rows: `12`
Counternegative rows: `12`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9634 passes, run a tiny episode-step structured probe; if it fails, construct more same-feature/different-label counterpositives.
