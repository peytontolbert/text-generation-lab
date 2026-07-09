# Stage9581 Residual Denoise Neutral Boundary Decision Manifest

Passed: `True`
Rows: `48`
Decision counts: `{'NO': 24, 'YES': 24}`
Generation prefix field: `model_input.repair_decision_prefix`

The target asks for `YES` when boundary-next-token repair is required and `NO` when only prefix repair is required.

Authorities remain closed and the only enabled loss is `denoise_ce`.
