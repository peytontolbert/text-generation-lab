# Stage9487 Full Episode With Observe-Prefix Manifest

Passed: `True`
Rows: `116`
Splits: `{'eval': 7, 'strict_eval': 7, 'train': 102}`
Loss counts: `{'episode_boundary_match_ce': 50, 'episode_failure_type_ce': 50, 'episode_repair_outcome_ce': 50, 'episode_step_value_mse': 50, 'episode_target_prefix_match_ce': 66}`

This manifest keeps the four pre-action episode heads on Stage9455 rows and moves `episode_target_prefix_match_ce` onto observe/verifier-phase rows with visible generated/reference evidence.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
