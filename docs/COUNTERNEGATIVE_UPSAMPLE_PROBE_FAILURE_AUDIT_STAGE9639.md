# Stage9639 Counternegative Upsample Probe Failure Audit

Passed: `True`
Stage9638 quality passed: `False`
Eval/strict joint: `0.7642857142857142` / `0.2857142857142857`
Positive wrong rows: `100`
Negative wrong rows: `0`
Wrong by field: `{'episode_boundary_match': 30, 'episode_failure_type': 32, 'episode_repair_outcome': 27, 'episode_step_value': 22, 'episode_target_prefix_match': 22}`

Counternegative upsampling reduced shortcut baselines but made the five-head mixed objective over-reject positives. The next stage should split observe-phase supervision into isolated boundary/target-prefix heads before recombining repair_outcome/failure/value.

Next: Build Stage9640 per-head isolated observe manifest for episode_boundary_match and episode_target_prefix_match only; shortcut-audit before any target-100M run.
