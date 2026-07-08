# Stage9460 Episode-Step Target-100M Tiny Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Strict joint proxy exact: `0.2`
Eval joint proxy exact: `1.0`
Wrong by field: `{'episode_failure_type': 1, 'episode_repair_outcome': 1, 'episode_step_value': 1, 'episode_target_prefix_match': 1}`

Safe target-100M structured execution worked, but strict row predicts the successful prior for residual outcome/failure/value. Next curriculum should add observation-conditioned diagnosis or more contrastive residual support before widening.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
