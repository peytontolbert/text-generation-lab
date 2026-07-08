# Stage9409 Structured Suffix Route Manifest

Passed: `True`
Rows: `31`
Splits: `{'eval': 9, 'strict_eval': 7, 'train': 15}`
Routes: `{'assertion_constant_route': 3, 'checked_symbol_evidence_route': 3, 'current_invariant_route': 3, 'dependency_constraint_route': 3, 'generic_suffix_route': 4, 'localized_edit_target_route': 3, 'localized_repair_route': 2, 'repaired_state_route': 3, 'verified_patch_operator_route': 3, 'whitelist_patch_route': 2, 'wrapper_plan_route': 2}`

This branches from Stage9397 and excludes the interfering Stage9401/9405 rows. It adds route controls to model input but does not add new suffix target prose.
