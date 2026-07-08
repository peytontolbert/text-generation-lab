# Stage9255 Precomputed Repo-State Transformation Spine

Passed: `True`

Core thesis: software maintenance should be trained as task-conditioned transformations over a precomputed repo state, not as raw-context code completion.

State equations:
- `repo_compilation`: `Repo -> Psi_R`
- `task_observable`: `Task -> O_q`
- `maintenance_state`: `S_t = Contract(Psi_R, O_q, h_t)`
- `policy_action`: `a_t = pi_theta(S_t)`
- `incremental_update`: `Psi_R -> Psi_{R+Delta} after patch/test feedback`

Precomputable repo layers:
- `ast_cst_structure`
- `symbol_table`
- `import_export_graph`
- `call_graph`
- `dataflow_graph`
- `type_signature_schema_map`
- `test_coverage_graph`
- `runtime_error_index`
- `historical_cochange_graph`
- `patch_affordance_index`
- `blast_radius_map`
- `module_boundary_cache`
- `dependency_capability_cards`
- `task_class_operator_bases`

Online task-time components:
- `task_intent_observable`
- `current_agent_history`
- `active_causal_subgraph`
- `patch_or_action_choice`
- `verifier_feedback_update`

This stage is architecture/control-plane only. It opens no model execution, training, runtime, Gemma, harness, scoring, mining, source/body emission, cleanup, controller merge, or promotion.

Next: Build a repo_state_compiler_cache_manifest design that materializes Psi_R layers without reading /arxiv or opening runtime/training.
