# Stage9513 Episode Observation Diagnosis Counterbalance Repair Manifest

Passed: `True`
Rows: `58`
Split counts: `{'train': 46, 'eval': 6, 'strict_eval': 6}`
Repair focus rows: `['stage9513_obs_diag_repair_0047', 'stage9513_obs_diag_repair_0048']`

This patch exposes primitive observation evidence under neutral `obs_*` model-input features. It does not expose `effective_*` authority labels in `model_input`.

The target is to fix the Stage9511 high-confidence eval failures where the model inferred verifier outcome from pre-action context instead of observed residual facts.
