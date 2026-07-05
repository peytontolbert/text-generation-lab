# Stage8858 Model Interpretability Telemetry Gap Audit

## Status

Stage8858 audits whether the recovered 100M training/probe path has enough model-internal telemetry to diagnose failures before reopening training or decoder CE.

Passed: `True` as an audit.

Authority remains closed:

- model execution: `False`
- decoder CE training: `False`
- denoise CE training: `False`
- runtime: `False`
- source/body emission: `False`
- Gemma/harness/scoring: `False`
- promotion: `False`

## What We Have Recovered

The repo now has a strong telemetry substrate.

### Training Telemetry

Recovered modules:

- `scripts/training_telemetry_metrics.py`
- `scripts/training_telemetry.py`
- `scripts/structured_telemetry_contract.py`
- `legacy_src/agentkernel_lite/training_loop.py`

Covered signals:

- `loss_by_step.jsonl`
- `eval_loss_by_checkpoint.jsonl`
- `row_field_logits.jsonl`
- `row_field_losses.jsonl`
- `row_token_loss.jsonl`
- `module_delta_norms.json`
- `failure_bucket_card.json`
- confidence/margin/entropy helpers
- high-confidence-wrong row detection
- token loss map helper

### Gradient And Activation Interpretability

Recovered module:

- `scripts/gradient_activation_interpretability.py`

Covered helpers:

- row gradient norm by parameter/module
- module delta norm by parameter/module
- activation cache summaries
- feature ablation attribution
- activation patch recovery cards
- bundle completeness card

### Dataset Dynamics

Recovered module:

- `scripts/dataset_cartography_active_learning.py`

Covered signals:

- confidence mean/variance
- loss mean/variance
- forgetting events
- noisy label routing
- easy redundant downsampling
- hard/ambiguous neighbor generation routing

### Training Data Attribution

Recovered module:

- `scripts/training_data_attribution_influence.py`

Covered signals:

- eval-row to train-row helpful neighbors
- harmful/conflicting train rows
- missing-neighborhood detection
- weak/ambiguous influence
- dataset patch recommendations

### Confidence/OOD/Drift

Recovered docs/modules:

- `CONFIDENCE_OOD_HEAD_CONTRACT_READINESS_STAGE8735`
- `DRIFT_CANARY_REGRESSION_MONITOR_READINESS_STAGE8750`
- `SCHEMA_DRIFT_DETECTOR_READINESS_STAGE8754`
- `TRACED_EVAL_OBSERVABILITY_READINESS_STAGE8786`

Covered concepts:

- confidence/OOD heads
- drift canary regression monitor
- schema drift detector
- trace observability

## What Is Not Yet Enough

The telemetry substrate exists, but the actual native probe outputs are not yet rich enough.

### Gap 1: Structured Head Logits Are Too Thin

Current structured probe writes:

- row id
- field
- target
- prediction
- correct
- margin

Missing:

- full logits or top-k logits
- softmax confidence
- entropy
- top-2 label
- calibrated confidence
- high-confidence-wrong flag
- per-cell confidence summary

Why it matters:

For action/evidence/build-policy heads, a low-margin error means a data boundary issue. A high-confidence wrong prediction means a bad shortcut, label, feature surface, or loss weighting problem.

Required artifact upgrade:

`row_field_logits.jsonl` should include:

```json
{
  "row_id": "...",
  "split": "strict_eval",
  "field": "build_mode",
  "target": "BUILD_ON_TOP",
  "pred": "USE_WHITELIST_IMPORT",
  "correct": false,
  "top1_logit": 2.4,
  "top2_logit": 2.1,
  "top1_label": "USE_WHITELIST_IMPORT",
  "top2_label": "BUILD_ON_TOP",
  "margin": 0.3,
  "confidence": 0.42,
  "entropy": 1.04,
  "high_confidence_wrong": false,
  "operation_cell": "python.repo_repair.build_on_top"
}
```

### Gap 2: Decoder Row Token Loss Is Not Real Per-Token CE Yet

The bounded decoder CE probe currently writes `row_token_loss.jsonl`, but it records target metadata rather than a full per-position CE map.

Missing:

- token position
- token id
- decoded token text
- target token
- loss per token
- EOS position
- high-loss span
- internal/control-token logit probability
- repeated-token loss cluster

Why it matters:

Decoder failures are token-local: early EOS, repetition, missing prefix, wrong code fence, internal-token leakage, malformed patch hunk. Aggregate CE will not tell us where the decode failed.

Required artifact:

`row_token_loss.jsonl` should contain one record per row with a `positions` list from `token_loss_map(...)`.

### Gap 3: Gradient Norms Are Step-Level, Not Row-Level

Current loop logs `grad_norm` per step and module deltas after training.

Missing:

- per-row gradient norm
- per-row gradient norm by module
- head-specific gradient norm
- decoder-vs-encoder gradient split
- gradient conflict indicators across rows/cells

Why it matters:

The curriculum compiler must know whether a few rows dominate updates, whether decoder gradients are accidentally active, and whether one head is drowning out another.

Required artifact:

`row_gradient_norms.jsonl`

Minimum fields:

- `row_id`
- `losses_enabled`
- `total_grad_norm`
- `grad_norm_by_module`
- `decoder_grad_norm`
- `structured_head_grad_norm`
- `encoder_grad_norm`

### Gap 4: Activation Capture Is Not Wired Into Native Probes

The helper exists, but the trainer does not yet save activation caches.

Missing:

- pooled encoder hidden state
- encoder layer 0 summary
- encoder middle layer summary
- encoder final layer summary
- field-head input
- decoder hidden summary for bounded CE rows

Why it matters:

If a structured head fails, we need to know whether the representation exists in the encoder and the head cannot read it, or whether the encoder never formed the feature.

Required artifacts:

- `activation_cache_index.json`
- `activation_cache.pt` or compact parquet/npz
- `activation_summary.jsonl`

### Gap 5: Feature Ablation Is Not Automated

The feature ablation helper exists, but native probes do not yet run controlled ablations over input groups.

Missing ablation groups:

- user intent
- import/dependency evidence
- repo graph evidence
- symbol binding evidence
- test/failure evidence
- budget/length features
- surface/role features
- verifier feedback
- junk/ranker route bits

Why it matters:

This answers whether the model used the intended evidence or a shortcut.

Required artifact:

`feature_ablation_attribution.jsonl`

### Gap 6: Activation Patching Is Not Current-Objective Ready

Recovered activation patching is a helper contract, not a current objective runner.

Missing:

- clean/corrupt row pairing builder
- layer selection
- field-specific logit recovery metric
- pair cells for build mode, symbol binding, edit localization, patch operator, verifier repair

Why it matters:

Activation patching is the strongest test that the model internally represents a causal feature rather than only fitting labels.

Required artifact:

`activation_patch_recovery.jsonl`

### Gap 7: Parameter Delta Audit Needs Module Buckets

Current `module_delta_norms.json` records parameter-level deltas, but not enough semantic grouping.

Missing groups:

- embeddings
- encoder attention
- encoder MLP
- decoder attention
- decoder MLP
- LM head
- structured heads
- retrieval heads
- confidence/OOD heads

Why it matters:

For structured-only probes, decoder deltas should be zero or near-zero if frozen/unused. If decoder weights move during structured-only training, loss masks are broken.

### Gap 8: Dataset Cartography Is Not Fed Back Automatically

Dataset cartography can classify examples, but the native probe does not yet produce the history needed for robust forgetting/loss variance.

Missing:

- row confidence history across checkpoints
- row loss history across checkpoints
- row correct history across checkpoints
- row prediction flip count
- forgetting count by row and cell

Required artifact:

`row_dynamics_history.jsonl`

### Gap 9: Influence Attribution Is Still Heuristic

Training-data attribution exists, but it currently uses deterministic overlap/tag heuristics.

That is useful for recovery, but not enough once real probes run.

Future upgrade:

- use row embeddings or activation fingerprints
- compare train/eval gradient similarity
- identify harmful train rows by counterfactual removal or reweighting
- connect influence type to concrete dataset patch queues

### Gap 10: Probe Gate Must Fail If Telemetry Is Missing

The strongest missing integration is not another metric. It is enforcement.

Every future native probe should fail if required telemetry artifacts are absent, empty, or schema-invalid.

Required gate:

```text
required_interpretability_artifacts_present == true
row_field_logits_has_confidence_entropy == true
row_token_loss_has_positions == true
module_delta_has_decoder_delta == true
row_gradient_norms_present == true
activation_summary_present for structured probes
feature_ablation_present for model-ready probes
```

## Required Probe Artifact Set

For structured-head probes:

- `loss_by_step.jsonl`
- `eval_loss_by_checkpoint.jsonl`
- `row_field_logits.jsonl`
- `row_field_losses.jsonl`
- `row_gradient_norms.jsonl`
- `field_confusion_matrix.json`
- `field_exact_by_cell.json`
- `feature_ablation_attribution.jsonl`
- `activation_summary.jsonl`
- `module_delta_norms.json`
- `row_dynamics_history.jsonl`
- `failure_bucket_card.json`

For bounded decoder CE probes:

- `loss_by_step.jsonl`
- `eval_loss_by_checkpoint.jsonl`
- `row_token_loss.jsonl`
- `eos_length_audit.json`
- `internal_token_logit_summary.json`
- `short_output_probe.json`
- `repetition_probe.json`
- `sample_generation_audit.json`
- `row_gradient_norms.jsonl`
- `decoder_activation_summary.jsonl`
- `module_delta_norms.json`
- `failure_bucket_card.json`

## Diagnosis Map

Use telemetry to route failures:

- low-margin wrong: add contrastive neighbors
- high-confidence wrong: inspect label/shortcut/feature leak
- high entropy: evidence insufficient or representation weak
- high row gradient: row dominates update; inspect source/label
- decoder delta during structured-only probe: loss-mask violation
- encoder representation linearly separable but head fails: head/loss issue
- representation not separable: feature/schema/curriculum issue
- token loss spike at EOS: EOS/length objective issue
- token loss spike at control token: leakage/suppression issue
- repeated-token loss cluster: repetition objective issue
- harmful influence cluster: quarantine/downweight conflicting train rows

## Next

Next best step:

`stage8859_native_probe_interpretability_artifact_contract`

It should define schemas and gate checks for the required artifacts before any next native probe. Do not run a model yet.
