# Stage9488 Full Episode Observe-Prefix Preflight Audit

Passed: `True`
Execution authorized for next stage: `True`
Rows: `116`
Splits: `{'eval': 7, 'other': 0, 'strict_eval': 7, 'train': 102}`
Loss counts: `{'action_sequence_ce': 0, 'allowed_import_policy_ce': 0, 'blocked_import_policy_ce': 0, 'build_mode_ce': 0, 'decoder_ce': 0, 'denoise_ce': 0, 'edit_localization_ce': 0, 'episode_boundary_match_ce': 50, 'episode_failure_type_ce': 50, 'episode_repair_outcome_ce': 50, 'episode_step_value_mse': 50, 'episode_target_prefix_match_ce': 66, 'file_plan_ce': 0, 'patch_operator_ce': 0, 'repair_surface_ce': 0, 'repo_dependency_policy_ce': 0, 'runtime_reward': 0, 'suffix_choice_ce': 0, 'surface_role_ce': 0, 'symbol_binding_ce': 0, 'verifier_repair_ce': 0}`

Only structured episode-step losses are open. Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, and promotion remain closed.
