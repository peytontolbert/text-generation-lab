# Stage9493 Per-Head Verifier Curriculum Queue

Passed: `True`
Rows: `330`
Splits: `{'eval': 30, 'strict_eval': 30, 'train': 270}`
Loss counts: `{'episode_boundary_match_ce': 66, 'episode_failure_type_ce': 66, 'episode_repair_outcome_ce': 66, 'episode_step_value_mse': 66, 'episode_target_prefix_match_ce': 66}`

Each row enables exactly one verifier loss. This is a queue for isolated probes, not a model-execution authorization.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
