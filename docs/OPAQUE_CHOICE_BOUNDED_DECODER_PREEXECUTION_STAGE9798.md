# Stage9798 Opaque Choice Bounded Decoder Preexecution

Passed: `True`
Rows: `60`
Splits: `{'eval': 20, 'strict_eval': 20, 'train': 20}`
Languages: `{'c_cpp': 15, 'python': 15, 'rust': 15, 'web_js_ts_html': 15}`
Losses: `{'action_sequence_ce': 0, 'allowed_import_policy_ce': 0, 'blocked_import_policy_ce': 0, 'build_mode_ce': 0, 'decoder_ce': 60, 'denoise_ce': 0, 'edit_localization_ce': 0, 'episode_boundary_match_ce': 0, 'episode_failure_type_ce': 0, 'episode_repair_outcome_ce': 0, 'episode_step_value_mse': 0, 'episode_target_prefix_match_ce': 0, 'file_plan_ce': 0, 'patch_operator_ce': 0, 'repair_surface_ce': 0, 'repo_dependency_policy_ce': 0, 'runtime_reward': 0, 'suffix_choice_ce': 0, 'surface_role_ce': 0, 'symbol_binding_ce': 0, 'verifier_repair_ce': 0}`
Command ready: `True`

This stage opens exactly one bounded decoder CE execution ticket on the corrected opaque-choice surface. It is intended to test whether decoder-side learning improves the multilingual comparison without reintroducing leakage or generation collapse.

Next: Execute Stage9799 bounded decoder CE probe under trellis, then compare it against Stage9794 and Gemma on the same strict-eval rows before deciding whether decoder CE improved the multilingual head-to-head position.

