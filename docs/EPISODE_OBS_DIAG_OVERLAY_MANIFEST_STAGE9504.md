# Stage9504 Episode Observation Diagnosis Overlay Manifest

Passed: `True`
Rows: `58`
Loss counts: `{'episode_failure_type_ce': 58, 'episode_repair_outcome_ce': 58, 'episode_step_value_mse': 58}`

This manifest restores the trainable observation-diagnosis heads that previously passed best-state selection, while attaching deterministic verifier overlay metadata outside `model_input`.

Enabled losses are limited to `episode_failure_type_ce`, `episode_repair_outcome_ce`, and `episode_step_value_mse`. Boundary and target-prefix remain deterministic effective verifier facts, not learned authority.
