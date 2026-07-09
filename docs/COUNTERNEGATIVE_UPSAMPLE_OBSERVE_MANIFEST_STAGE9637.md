# Stage9637 Counternegative Upsample Observe Manifest

Passed: `True`
Rows: `84`
Counternegative / counterpositive rows: `24` / `12`
Splits: `{'train': 28, 'eval': 28, 'strict_eval': 28}`
Strongest single-feature baseline: `0.6666666666666666` via `source_stage->target_prefix_match`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9637 passes, run Stage9638 tiny episode-step structured probe; otherwise add same-feature/different-label rows until shortcut baselines drop below 0.75.
