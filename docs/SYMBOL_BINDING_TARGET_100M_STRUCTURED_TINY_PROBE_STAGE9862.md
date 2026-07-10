# Stage9862 Symbol-Binding Target-100M Structured Tiny Probe Audit

Stage9862 records the first successful validity-weighted target-100M structured execution after the Stage9861 readiness gate.

This run executes the Stage9859 validity-weighted symbol-binding tiny manifest under the verified `trellis` runtime and freezes the resulting telemetry for comparison against the earlier Stage9698 baseline.

## Result

- Execution/telemetry passed: `True`
- Quality passed: `False`
- Promotion ready: `False`
- Parameter count: `102717225`
- Eval exact: `0.3125`
- Strict exact: `0.3125`
- Decoder delta norm: `0.0`

## Boundary

- Decoder CE stayed closed.
- Model execution ran under `trellis`; Gemma, harness, and final checkpoint export stayed closed.
- Decoder, LM head, and embedding buckets stayed frozen.

## Next

Build Stage9863 post-run diagnostics and historical comparison for validity-weighted symbol binding: inspect confusion matrix, row logits, feature ablations, gradient norms, and target/evidence balance before deciding whether to open the same execution path for edit-localization.
