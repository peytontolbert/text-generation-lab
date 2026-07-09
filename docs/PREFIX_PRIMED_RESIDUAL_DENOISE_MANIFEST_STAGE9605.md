# Stage9605 Prefix-Primed Residual Denoise Manifest

Passed: `True`
Rows: `26`
Holdout rows: `15`
Splits: `{'train': 20, 'eval': 3, 'strict_eval': 3}`
Generation prefix field: `model_input.active_generation_prefix_span`

This patches the Stage9603 failure mode by replacing symbolic decoder targets such as `REPAIR_PREFIX_ONLY :: ...` with the natural bounded clean target from `episode_transition.state_t_plus_1.decoder_text`.

The visible prefix is short and audited; the full target/suffix is not placed in model input. Decoder CE, runtime, Gemma, harness, checkpoint export, and promotion remain closed.

Next: Run Stage9606 contract-only two-phase preflight with --phase2-manifest Stage9605 and --generation-prefix-field model_input.active_generation_prefix_span.
