# Stage9072 Trainer Dry-Run Recovered Contract

Passed: `True`

This is a no-execution documentation refresh for the recovered trainer dry-run contract. It records the required inputs, flags, hard stops, telemetry stubs, forbidden operations, and long-context blockers that must exist before a future contract-only trainer dry run can even be considered.

## Required Inputs

- `locked_tiny_training_manifest.jsonl`
- `loss_mask_card.json`
- `manifest_schema_lock.json`
- `trainer_contract_dry_run_input.json`
- `long_context_compiler_handoff_blocker_audit.json`
- `long_context_loss_mask_compiler_preflight.json`
- `long_context_route_card_materialization_audit_contract.json`
- `training_readiness_refresh_after_long_context_controls.json`

## Required Hard Stops

- `dry_run_stops_before_model_forward`
- `no_model_weights_loaded`
- `no_optimizer_created`
- `no_backward_called`
- `no_dataset_row_body_loaded`
- `no_repository_source_body_loaded`
- `no_long_context_rows_loaded_without_source_ticket`
- `route_to_trainer_loss_translation_blocks_decoder_denoise_runtime`
- `no_final_checkpoint_export_path`

## Closed Now

- trainer invocation
- model forward
- row loading
- repository source/body loading
- candidate mining
- decoder CE
- denoise CE
- runtime
- /arxiv compiler IO
- training

Next: Continue no-data recovery with a central graph gap walk against Stage9072, or design a future source/output ticket without reading row bodies.
