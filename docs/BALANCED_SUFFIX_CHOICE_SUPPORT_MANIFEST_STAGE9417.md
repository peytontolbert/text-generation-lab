# Stage9417 Balanced Suffix Choice Support Manifest

Passed: `True`
Rows: `60`
Added train support rows: `29`
Splits: `{'eval': 9, 'strict_eval': 7, 'train': 44}`
Train choice counts: `{'checked_symbol_evidence__keep_decision_compatible': 4, 'current_repair_invariant__do_not_introduce': 4, 'dependency_constraint__keep_output_limited': 4, 'expected_assertion_behavior__keep_value_small': 4, 'generic_suffix_choice': 4, 'localized_edit_target__keep_path_reference': 4, 'localized_repair_step__keep_response': 4, 'repaired_state__keep_answer_focused': 4, 'verified_patch_operator__use_repo': 4, 'whitelist_patch__use_symbol': 4, 'wrapper_plan__keep_answer_focused': 4}`

This keeps decoder CE and denoise CE closed; it only balances structured suffix-choice control training.
