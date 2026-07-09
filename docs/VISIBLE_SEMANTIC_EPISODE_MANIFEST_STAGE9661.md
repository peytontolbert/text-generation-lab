# Stage9661 Visible Semantic Episode Manifest

Passed: `True`
Rows: `66`
Splits: `{'train': 48, 'eval': 9, 'strict_eval': 9}`
Loss counts: `{'episode_failure_type_ce': 66, 'episode_repair_outcome_ce': 66, 'episode_step_value_mse': 66}`
Label by split: `{'train': {'failure_type': {'not_exact+target_prefix_miss+boundary_next_token_miss+degenerate_repetition+unterminated': 2, 'none': 25, 'not_exact+target_prefix_miss': 13, 'not_exact+target_prefix_miss+boundary_next_token_miss+unterminated': 1, 'not_exact+target_prefix_miss+boundary_next_token_miss': 7}, 'repair_outcome': {'residual_suffix_repair_step': 23, 'successful_suffix_repair_step': 15, 'verified_target_prefix_positive': 10}, 'step_value': {'0.0': 23, '1.0': 25}}, 'eval': {'failure_type': {'not_exact+target_prefix_miss+boundary_next_token_miss': 2, 'not_exact+target_prefix_miss': 1, 'none': 6}, 'repair_outcome': {'residual_suffix_repair_step': 3, 'successful_suffix_repair_step': 3, 'verified_target_prefix_positive': 3}, 'step_value': {'0.0': 3, '1.0': 6}}, 'strict_eval': {'failure_type': {'not_exact+target_prefix_miss': 2, 'not_exact+target_prefix_miss+boundary_next_token_miss': 1, 'none': 6}, 'repair_outcome': {'residual_suffix_repair_step': 3, 'successful_suffix_repair_step': 3, 'verified_target_prefix_positive': 3}, 'step_value': {'0.0': 3, '1.0': 6}}}`
Single-feature baselines: `{'observed_boundary_prefix_pair->failure_type': 0.9545454545454546, 'observed_boundary_prefix_pair->repair_outcome': 0.7575757575757576, 'observed_boundary_prefix_pair->step_value': 1.0, 'observed_residual_reason_count->failure_type': 1.0, 'observed_residual_reason_count->repair_outcome': 0.7575757575757576, 'observed_residual_reason_count->step_value': 1.0, 'repair_attempt_kind->failure_type': 0.5606060606060606, 'repair_attempt_kind->repair_outcome': 0.6818181818181818, 'repair_attempt_kind->step_value': 0.6818181818181818, 'observed_success_relation->failure_type': 0.803030303030303, 'observed_success_relation->repair_outcome': 0.7575757575757576, 'observed_success_relation->step_value': 1.0}`
Combo baselines: `{'primitive_failure_bits->failure_type': 1.0, 'phase_plus_success->repair_outcome': 1.0, 'success_relation->step_value': 1.0}`

This stage exposes primitive observe/verifier bits to normalize episode failure type, repair outcome, and step value. Boundary/prefix heads are closed here because Stage9660 already passed them.

Decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, final checkpoint export, controller merge, and promotion remain closed.

Next: If Stage9661 passes, run Stage9662 visible semantic episode target-100M probe for failure/outcome/value heads.
