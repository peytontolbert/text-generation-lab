# Stage9662 Visible Semantic Episode Tiny Probe

Passed: `True`
Safety passed: `True`
Quality passed: `True`
Eval/strict joint: `1.0` / `1.0`
Eval field exact: `{'episode_failure_type': 1.0, 'episode_repair_outcome': 1.0, 'episode_step_value': 1.0}`
Strict field exact: `{'episode_failure_type': 1.0, 'episode_repair_outcome': 1.0, 'episode_step_value': 1.0}`
Wrong by field: `{}`

Decoder CE, denoise CE, runtime, Gemma, harness, checkpoint export, and promotion remained closed.

Next: If Stage9662 passes, rejoin all five episode observe/repair heads under a gated combined manifest; if it fails, inspect failure/outcome/value telemetry and patch semantic features.
