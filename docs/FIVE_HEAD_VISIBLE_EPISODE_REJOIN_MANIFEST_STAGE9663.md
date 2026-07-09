# Stage9663 Five-Head Visible Episode Rejoin Manifest

Passed: `True`
Rows: `66`
Splits: `{'train': 48, 'eval': 9, 'strict_eval': 9}`
Loss counts: `{'episode_boundary_match_ce': 66, 'episode_failure_type_ce': 66, 'episode_repair_outcome_ce': 66, 'episode_step_value_mse': 66, 'episode_target_prefix_match_ce': 66}`

This stage rejoins the two passed boundary/prefix heads with the three passed semantic episode heads on the same collator-visible observe/repair rows.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.

Next: If Stage9663 passes, run Stage9664 five-head visible episode target-100M rejoin probe.
