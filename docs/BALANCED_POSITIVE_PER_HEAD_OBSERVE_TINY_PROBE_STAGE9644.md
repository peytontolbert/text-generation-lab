# Stage9644 Balanced Positive Per-Head Observe Tiny Probe

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval/strict joint: `0.5` / `0.5`
Eval field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
Strict field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
Wrong by field: `{'episode_boundary_match': 28, 'episode_target_prefix_match': 28}`
High-confidence wrong rows: `0`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9644 passes, add repair_outcome as a separate follow-up; if it fails, audit whether row_id/source-family markers caused split memorization.
