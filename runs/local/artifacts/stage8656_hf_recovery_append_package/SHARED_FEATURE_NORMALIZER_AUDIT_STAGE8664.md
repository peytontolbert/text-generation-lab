# Stage8664 Shared Feature Normalizer Audit

Canonical alias map and schema-drift audit over recovered manifests.

## Metrics
- `rows_total`: `4308`
- `manifests`: `7`
- `alias_count`: `43`
- `missing_aliases`: `[]`
- `old_authority_alias_hits`: `1068`
- `failures`: `[]`
- `model_execution_authorized_next`: `False`
- `decoder_ce_training_authorized_next`: `False`
- `denoise_ce_training_authorized_next`: `False`
- `runtime_authorized`: `False`
- `promotion_ready`: `False`

## Boundary
Forbidden authority/loss paths must remain false: `decoder_ce`, `denoise_ce`, `runtime_reward`, model/runtime/source/body authorities.
