# Stage9466 Episode Observation Diagnosis Micro Target-100M Probe Audit

Passed: `True`
Safety passed: `True`
Quality passed: `True`
Eval joint proxy exact: `1.0`
Strict joint proxy exact: `1.0`
Strict loss: `0.0012421851279214025`

Target-100M can learn the observation-diagnosis success/residual rule when the train schedule repeatedly covers both cells. Stage9463 failure is therefore schedule/cap exposure, not an impossible representation or missing label problem.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
