# Stage9047 Domain/Twin Schema Compiler Audit

Passed: `True`

Domain/Twin metadata records are source metadata, not direct compiler rows.
A future adapter must add route, semantic key, gate status, authority, anti-cheat, provenance, and loss masks before compiler use.
This stage emits no adapter output and opens no mining/training authority.

Required adapter outputs:

- `domain_twin_judged_rows.jsonl`
- `domain_twin_gate_status_card.json`
- `domain_twin_loss_mask_card.json`
- `domain_twin_shortcut_audit.json`
- `domain_twin_compiler_audit_card.json`

Adapter rules:

- `source_metadata_records_must_not_be_compiler_rows_directly`
- `adapter_must_assign_objective_aware_route`
- `adapter_must_emit_complete_gate_status`
- `adapter_must_emit_all_losses_disabled_by_default`
- `adapter_must_emit_semantic_key_without_body_text`
- `adapter_must_preserve_authority_closed`
- `adapter_must_run_shortcut_baselines_before_training`

Next: Design a synthetic fixture-only Domain/Twin adapter validator that emits compiler-shaped rows with closed loss masks and complete gate_status; do not materialize real records.

