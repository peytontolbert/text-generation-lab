# Stage9044 Semantic Intent Surface Bridge

Passed: `True`

This contract promotes recovered semantic-presentation and user-intent fields into the active maintainer row schema.
It does not mine data, read `/arxiv` bodies, materialize rows, run models, or authorize training.

## Semantic Surfaces

- `maintainer_answer`
- `repair_plan`
- `bounded_patch_hunk`
- `test_plan`
- `repo_qa_answer`
- `retrieve_more_answer`
- `abstain_unsafe_answer`
- `verifier_failure_summary`
- `symbol_binding_decision`
- `edit_localization_decision`
- `patch_operator_decision`

## User Intent Fields

- `intent_type`
- `requested_output_type`
- `target_language`
- `repo_scope`
- `allowed_imports`
- `blocked_imports`
- `available_repositories`
- `file_creation_allowed`
- `modify_existing_allowed`
- `test_required`
- `verification_mode`
- `risk_tolerance`
- `budget_constraints`

## Anti-Cheat Requirements

- `semantic_presentation_not_equal_objective_label`
- `requested_output_type_not_equal_target_action`
- `intent_type_alone_must_not_solve_build_mode`
- `presentation_surface_alone_must_not_solve_repair_surface`
- `direct_target_markers_masked_or_neutralized`
- `shortcut_baseline_required_for_intent_and_surface_fields`
- `counterfactual_sibling_required_when_intent_surface_changes`

Next: When future source tickets pass, require semantic_presentation/user_intent shortcut audits before any intent-to-build or bounded-decoder manifest can create gradients.

