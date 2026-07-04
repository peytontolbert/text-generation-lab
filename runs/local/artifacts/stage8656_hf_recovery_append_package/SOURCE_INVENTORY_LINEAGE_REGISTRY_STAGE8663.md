# Stage8663 Source Inventory Lineage Registry

Executable source lineage registry derived from Stage8660.

## Metrics
- `source_records`: `36`
- `source_groups`: `7`
- `train_eligible_records`: `24`
- `locked_eval_records`: `5`
- `non_training_records`: `12`
- `parquet_files_indexed`: `184`
- `failures`: `[]`
- `model_execution_authorized_next`: `False`
- `decoder_ce_training_authorized_next`: `False`
- `denoise_ce_training_authorized_next`: `False`
- `runtime_authorized`: `False`
- `promotion_ready`: `False`

## Boundary
Locked-eval sources are explicitly `train_eligible=false` and carry `blocked_training_reason=locked_eval_source_never_mined_into_training`.
