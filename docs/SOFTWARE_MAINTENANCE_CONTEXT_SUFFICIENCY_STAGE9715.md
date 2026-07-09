# Stage9715 Software Maintenance Context Sufficiency Audit

Stage9715 checks whether the current trainer path actually gives the 100M maintainer model task-closed software evidence.

## Finding

- Training blocked by context sufficiency: `True`
- Trainer default max encoder tokens: `256`
- `build_batch` default max encoder tokens: `256`
- `_row_text` serializes `context_rows`: `False`

## Blockers

- `trainer_default_max_encoder_tokens_toy:256`
- `build_batch_default_max_encoder_tokens_toy:256`
- `row_text_does_not_serialize_context_rows`
- `long_context_pack_training_rows_drop_context_roles`
- `long_context_pack_first_context_not_local_evidence`
- `active_symbol_binding_manifests_have_no_context_rows`

## Next

Patch the context compiler/trainer handoff so maintenance rows carry role-preserved, task-closed context_rows into encoder text; then rerun this sufficiency audit before more target-100M probes.
