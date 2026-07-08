# Stage9416 Suffix Choice Control Failure Diagnosis

Stage9415 is safety-clean but quality-failed.

Low train label coverage: `{'dependency_constraint__keep_output_limited': 2, 'localized_repair_step__keep_response': 1, 'wrapper_plan__keep_answer_focused': 1, 'expected_assertion_behavior__keep_value_small': 1, 'verified_patch_operator__use_repo': 1, 'repaired_state__keep_answer_focused': 1, 'localized_edit_target__keep_path_reference': 1, 'current_repair_invariant__do_not_introduce': 1, 'whitelist_patch__use_symbol': 1, 'checked_symbol_evidence__keep_decision_compatible': 1}`
Heldout prediction counts: `{'generic_suffix_choice': 15, 'wrapper_plan__keep_answer_focused': 1}`

Next: balanced suffix-choice train support, then rerun structured control. Decoder and denoise generation remain closed.
