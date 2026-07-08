# Stage9461 Episode-Step Observation Diagnosis Manifest

Passed: `True`
Rows: `50`
Train losses: `['episode_failure_type_ce', 'episode_repair_outcome_ce', 'episode_step_value_mse']`
Disabled losses: `['episode_boundary_match_ce', 'episode_target_prefix_match_ce']`

This manifest changes the task from pre-action outcome guessing to verifier-observation diagnosis. It exposes neutral raw observation booleans and buckets, but not generated text, residual reason labels, decoder text, target suffix, reward, failure_type, or repair_outcome as input.
