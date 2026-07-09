# Stage9699 Symbol-Binding Post-Run Diagnostics

Stage9699 diagnoses the first target-100M source-backed symbol-binding probe. It does not authorize more execution.

## Findings

- Eval+strict exact: `0.3125`
- Prediction collapse: `BIND_CALL_TO_SYMBOL` at `1.0`
- Labels missing from eval or strict: `['BIND_IMPORT_TO_MODULE']`
- Loss increased from first to last step: `True`
- Decoder gradient nonzero rows: `0`
- Feature ablation telemetry is present but currently proxy-based, not native grouped masking.

## Repair Direction

Stage9700 should recompile the symbol-binding surface with complete split label coverage, add non-call contrastive rows, and upgrade native grouped feature ablations before any further target-100M execution.
