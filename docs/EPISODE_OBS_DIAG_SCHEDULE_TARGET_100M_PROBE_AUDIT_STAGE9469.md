# Stage9469 Episode Observation Diagnosis Schedule Target-100M Probe Audit

Passed: `False`
Safety passed: `True`
Quality passed: `False`
Eval joint proxy exact: `0.3333333333333333`
Strict joint proxy exact: `1.0`
Wrong by split/field: `{'eval::episode_repair_outcome': 1, 'eval::episode_step_value': 1}`

The 96-step full-manifest schedule fixed strict residual exactness but overcorrected eval success outcome/value with low margins. Next stage should add balanced eval/strict support or checkpoint-selection/early-stop telemetry rather than opening decoder CE.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
