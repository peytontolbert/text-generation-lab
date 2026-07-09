# Stage9540 Episode Observation Diagnosis Component Overlay Audit

Passed: `True`
Rows: `58`
Split counts: `{'train': 46, 'eval': 6, 'strict_eval': 6}`
Loss counts: `{'episode_failure_type_ce': 58, 'episode_repair_outcome_ce': 58, 'episode_step_value_mse': 58}`
Failure type counts: `{'not_exact+target_prefix_miss': 16, 'none': 29, 'not_exact+target_prefix_miss+boundary_next_token_miss': 10, 'not_exact+target_prefix_miss+boundary_next_token_miss+degenerate_repetition+unterminated': 2, 'not_exact+target_prefix_miss+boundary_next_token_miss+unterminated': 1}`

The audit verifies that Stage9539 composes `effective_failure_type` from observation residual components and leaves learned failure-type prediction as telemetry only.

No execution, decoder CE, denoise CE, runtime, harness, Gemma, controller merge, or promotion authority is opened.
