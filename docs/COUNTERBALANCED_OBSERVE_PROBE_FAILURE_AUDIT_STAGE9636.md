# Stage9636 Counterbalanced Observe Probe Failure Audit

Passed: `True`
Stage9635 quality passed: `False`
Strict joint proxy exact: `0.5`
High-confidence wrong rows: `57`
Counternegative wrong rows: `40`
Counternegative wrong by field: `{'episode_boundary_match': 8, 'episode_failure_type': 8, 'episode_repair_outcome': 8, 'episode_step_value': 8, 'episode_target_prefix_match': 8}`

The model over-accepts counternegative observe rows, predicting boundary/target true and verified/none with high confidence. The next data patch must upsample same-feature negative observations and separate boundary-token mismatch from verified target text before rerunning.

Next: Build Stage9637 counternegative upsample manifest with same source/guard/length buckets but different boundary/target labels; run shortcut audit before another tiny probe.
