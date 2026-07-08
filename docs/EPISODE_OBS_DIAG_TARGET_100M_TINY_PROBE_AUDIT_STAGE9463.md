# Stage9463 Episode Observation Diagnosis Target-100M Tiny Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval joint proxy exact: `1.0`
Strict joint proxy exact: `0.0`
Wrong by field: `{'episode_failure_type': 1, 'episode_repair_outcome': 1, 'episode_step_value': 1}`

Observation diagnosis exposed a discriminating prefix-alignment feature, but the 16-step target-100M probe still learned the success prior and failed the strict residual row. Next step should be a controlled two-cell/micro-overfit probe or stronger residual weighting before widening.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
