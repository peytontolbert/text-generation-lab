# Stage9645 Balanced Per-Head Probe Failure Audit

Passed: `True`
Strict field exact: `{'episode_boundary_match': 0.5, 'episode_target_prefix_match': 0.5}`
High-confidence wrong rows: `0`
All eval/strict predictions false: `True`
Top wrong pairs: `{'eval::episode_boundary_match::true=>false': 14, 'eval::episode_target_prefix_match::true=>false': 14, 'strict_eval::episode_boundary_match::true=>false': 14, 'strict_eval::episode_target_prefix_match::true=>false': 14}`

Stage9644 removed the high-confidence false collapse but still predicted false for every eval/strict boundary and target-prefix row. The next patch should not recombine heads. It should first prove a micro-overfit on a much smaller balanced per-head subset, or add stronger non-label positive evidence features before another 84-row target-100M run.

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Build Stage9646 micro-overfit per-head boundary/prefix subset with 4 train, 4 eval, 4 strict rows and stronger positive evidence; require train/eval exact before returning to 84-row balance.
