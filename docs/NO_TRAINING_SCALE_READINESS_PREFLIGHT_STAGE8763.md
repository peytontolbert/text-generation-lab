# Stage8763 No-Training Scale Readiness Preflight

Passed: `True`

This preflight compiled synthetic rows through `--require-recovered-gates` semantics without opening decoder CE, denoise CE, runtime reward, model execution, or authority.

- Gate rejected rows: `3`
- Objective counts: `{'structured_state': 1, 'bounded_decoder_ce': 1, 'human_review': 3}`
- Loss counts: `{'surface_role_ce': 1, 'repair_surface_ce': 1, 'build_mode_ce': 1, 'allowed_import_policy_ce': 1, 'blocked_import_policy_ce': 1, 'repo_dependency_policy_ce': 1, 'action_sequence_ce': 1, 'file_plan_ce': 1, 'symbol_binding_ce': 1, 'edit_localization_ce': 1, 'patch_operator_ce': 1, 'verifier_repair_ce': 1, 'decoder_ce': 0, 'denoise_ce': 0, 'runtime_reward': 0}`

Failed or missing recovered gates route to `human_review` and cannot create gradients.
