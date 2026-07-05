# Stage8862 Native Probe Interpretability Artifact Contract

Stage8862 turns the Stage8858 interpretability gaps into concrete native probe artifacts and a reusable non-empty artifact gate. This is a telemetry/runtime-contract patch only. It does not authorize model execution, decoder CE training, runtime, Gemma, harness/scoring, controller merge, or promotion.

## Implemented Telemetry Hooks

The recovered trainer now writes richer telemetry from native probe paths:

- `row_field_logits.jsonl`: confidence, entropy, top-2 fields, top-k distribution, high-confidence-wrong flag, split, field, target, prediction, and cell key.
- `row_token_loss.jsonl`: real per-position decoder CE map with token id/text, per-token loss, EOS marker, repeated-token positions, gold-token probability, and internal/control-token flag.
- `row_gradient_norms.jsonl`: batch-shared gradient norms by semantic module bucket for every row in the active batch. True per-example gradients remain a later heavier mode; this artifact explicitly records `gradient_scope=batch_shared`.
- `activation_summary.jsonl`: pooled field-head input and decoder-logit tensor summaries for train/eval/strict rows.
- `feature_ablation_attribution.jsonl`: deterministic evidence-group attribution proxy so missing ablation telemetry cannot silently pass. Native feature-masking reruns remain a v2 upgrade.
- `activation_patch_recovery.jsonl`: current-objective field-head patching proxy from logged clean/corrupt logits. Full clean/corrupt activation replacement remains a later upgrade.
- `module_delta_norms.json`: semantic parameter delta buckets with decoder/lm-head delta guard fields.
- `row_dynamics_history.jsonl`: row-level loss/confidence history, forgetting event count, prediction flip count, and variance summaries.
- `field_exact_by_cell.json`: structured exactness grouped by field and recovered cell key.
- `internal_token_logit_summary.json`: bounded decoder target/internal-token probability mass summary.

## New Gate

`scripts/native_probe_interpretability_artifact_contract.py` audits a completed native probe output directory. It fails if required telemetry is missing, empty, or schema-shallow. It checks:

- non-empty required JSONL artifacts;
- confidence/entropy/top-k/high-confidence-wrong fields in `row_field_logits.jsonl`;
- real per-position `loss` entries in `row_token_loss.jsonl`;
- gradient norm bucket records;
- activation summaries;
- feature ablation and activation patch records;
- row dynamics records;
- semantic module delta buckets;
- decoder delta remains zero for structured-only probes.

## Boundary

This stage preserves the closed authority boundary. Contract-only trainer runs can still emit placeholders for static audits, but future native probe outputs must pass the new artifact gate before their metrics can be trusted.

## Remaining Upgrade

The current implementation intentionally distinguishes proxy telemetry from heavier native instrumentation. Still missing for v2:

- true per-example gradient norms instead of batch-shared row records;
- actual feature-masking forward reruns for ablation;
- true layer activation patching using clean/corrupt row pairs;
- influence attribution tied to gradient/embedding similarity instead of heuristic row linkage.

Those are upgrades, not blockers for making missing telemetry fail loudly now.
