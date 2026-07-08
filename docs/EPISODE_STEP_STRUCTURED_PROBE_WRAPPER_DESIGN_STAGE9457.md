# Stage9457 Episode-Step Structured Probe Wrapper Design

Passed: `True`

This design introduces `episode_step_structured_probe` as the future trainable structured-head mode for episode-step supervision.

Allowed losses:
- `episode_repair_outcome_ce`
- `episode_failure_type_ce`
- `episode_boundary_match_ce`
- `episode_target_prefix_match_ce`
- `episode_step_value_mse`

Forbidden losses remain `decoder_ce`, `denoise_ce`, and `runtime_reward`. Model execution, checkpoint export, runtime, source/body emission, Gemma, harness, scoring, controller merge, and promotion remain closed.

Next: patch the trainer command surface and audit it statically. Do not execute the probe from this stage.
