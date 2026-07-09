# Stage9490 Phase-Aware Episode Verifier Manifest

Passed: `True`
Rows: `66`
Splits: `{'eval': 6, 'strict_eval': 6, 'train': 54}`
Loss counts: `{'episode_boundary_match_ce': 66, 'episode_failure_type_ce': 66, 'episode_repair_outcome_ce': 66, 'episode_step_value_mse': 66, 'episode_target_prefix_match_ce': 66}`

All five episode verifier labels are now observe-phase verifier-normalization targets. Generated/reference output evidence and primitive verifier observations are visible; final labels remain hidden.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
