# Stage9578 Residual Denoise Boundary Prefix-Primed Manifest

Passed: `True`
Rows: `48`
Class counts: `{'BOUNDARY': 24, 'PREFIX': 24}`
Generation prefix field: `model_input.repair_decision_prefix`

The target now starts with a shared `REPAIR_SCOPE=` prefix. The next generated token is the boundary-vs-prefix decision.

Authorities remain closed and the only enabled loss is `denoise_ce`.
