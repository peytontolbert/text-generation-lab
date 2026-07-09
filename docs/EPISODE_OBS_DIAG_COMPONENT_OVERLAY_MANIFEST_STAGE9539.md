# Stage9539 Episode Observation Diagnosis Component Overlay Manifest

Passed: `True`
Rows: `58`
Split counts: `{'train': 46, 'eval': 6, 'strict_eval': 6}`
Failure type counts: `{'not_exact+target_prefix_miss': 16, 'none': 29, 'not_exact+target_prefix_miss+boundary_next_token_miss': 10, 'not_exact+target_prefix_miss+boundary_next_token_miss+degenerate_repetition+unterminated': 2, 'not_exact+target_prefix_miss+boundary_next_token_miss+unterminated': 1}`

This stage applies the Stage9538 contract to the Stage9525 residual-gate manifest.
`effective_verifier.effective_failure_type` is now composed deterministically from `episode_transition.observation_t.residual_reasons`.
The learned `episode_failure_type` head remains telemetry-only and does not authorize verifier outcomes.

Execution, decoder CE, denoise CE, runtime reward, harness, Gemma, controller merge, and promotion remain closed.
