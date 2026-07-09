# Stage9563 Residual Denoise Contract Preflight Audit

Passed: `True`
Rows: `41`
Loss counts: `{'action_sequence_ce': 0, 'allowed_import_policy_ce': 0, 'blocked_import_policy_ce': 0, 'build_mode_ce': 0, 'decoder_ce': 0, 'denoise_ce': 41, 'edit_localization_ce': 0, 'episode_boundary_match_ce': 0, 'episode_failure_type_ce': 0, 'episode_repair_outcome_ce': 0, 'episode_step_value_mse': 0, 'episode_target_prefix_match_ce': 0, 'file_plan_ce': 0, 'patch_operator_ce': 0, 'repair_surface_ce': 0, 'repo_dependency_policy_ce': 0, 'runtime_reward': 0, 'suffix_choice_ce': 0, 'surface_role_ce': 0, 'symbol_binding_ce': 0, 'verifier_repair_ce': 0}`
Next model execution authorized: `True`
Next denoise CE authorized: `True`

This stage ran only the trainer contract preflight with `--contract-only`; it did not train the model.
