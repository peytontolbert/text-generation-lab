# Stage9640 Per-Head Boundary Prefix Observe Manifest

Passed: `True`
Rows: `84`
Splits: `{'train': 28, 'eval': 28, 'strict_eval': 28}`
Enabled losses: `['episode_boundary_match_ce', 'episode_target_prefix_match_ce']`
Disabled losses: `['decoder_ce', 'denoise_ce', 'runtime_reward', 'episode_repair_outcome_ce', 'episode_failure_type_ce', 'episode_step_value_mse']`
Strongest non-boundary-pair single-feature baseline: `0.6666666666666666`
Strongest overall single-feature baseline: `0.9761904761904762` via `boundary_token_pair_visible->boundary_match`

The boundary token pair baseline is tracked as real visible evidence, not a metadata shortcut.

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: If Stage9640 passes, run Stage9641 tiny target-100M episode-step probe over only episode_boundary_match and episode_target_prefix_match; do not recombine repair/value heads yet.
