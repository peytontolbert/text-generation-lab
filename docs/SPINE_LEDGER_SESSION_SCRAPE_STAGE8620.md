# Stage8620 Spine And Ledger Session Scrape

Stage8620 adds a focused scrape over `~/.codex/sessions` for research-spine, ledger, frontier, curriculum, decoder, repo-graph, and telemetry terms. This is a recovery index, not a training authorization.

## Source Artifacts

- Summary: `runs/local/artifacts/stage8620_spine_ledger_session_scrape/spine_ledger_session_scrape_summary.json`
- Snippets: `runs/local/artifacts/stage8620_spine_ledger_session_scrape/spine_ledger_session_snippets.jsonl`
- Files scanned: `260`
- Files with hits: `246`

## Hit Counts

The compact scrape found:

- `ledger`: `2317`
- `training_telemetry`: `1106`
- `decoder_branch`: `800`
- `curriculum_compiler`: `429`
- `frontier`: `106`
- `repo_graph`: `75`

The large `ledger` count matters. It confirms that run/stage ledgers were a major source of prior state and should be treated as a first-class recovery input, alongside docs and stage summaries.

## Highest-Signal Existing Recovery Docs

The grep confirmed that these recovered docs should be considered active spine material:

- `docs/recovery_v27_100m/00_central_research_spine.md`
- `docs/recovery_v27_100m/03_curriculum_compiler_and_dataset_judge.md`
- `docs/recovery_v27_100m/09_long_stage_timeline_reconstruction.md`
- `docs/recovery_v27_100m/10_objective_readiness_map.md`
- `docs/recovery_v27_100m/11_decoder_stage_deep_reconstruction.md`
- `docs/CURRENT_RESEARCH_SPINE_RECONSTRUCTED.md`
- `docs/RECOVERED_VARIABLE_LEDGER_STAGE8615.md`
- `docs/RECOVERED_TRAINING_MINING_GAP_MATRIX_STAGE8616.md`

The current rebuild should not ignore these files. They hold details that are not all present in executable scripts.

## Reconfirmed Central Spine

The durable path remains:

```text
intent-to-build strategy
-> repo_state_graph_v1
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decoder arguments
-> bounded decoder CE probe
-> measured decoder repair
-> scale judged curriculum
-> controlled maintainer loop
-> product/harness integration
```

The core law remains:

```text
train safe software transitions
then allow bounded decode
then repair decode through verifier feedback
then scale only judged rows
```

Do not revert to raw-code mining followed by decoder training.

## Reconfirmed Curriculum Compiler Laws

The session/doc scrape reinforces these compiler constraints:

- Every active row needs a canonical schema, action/semantic label, evidence state, surface family, operation cell, authority lane, route, loss mask, split/cell coverage, no leakage, and no shortcut dominance.
- Counterfactual obligations remain mandatory for active training rows:
  - positive original,
  - evidence removed / retrieve,
  - contradictory or unsafe twin,
  - mixed replay where applicable.
- Static compiler correctness does not imply learned model capability.
- Metadata-only, single-feature, combo-feature, surface-marker, request-marker, query-ID, and graph-degree shortcuts must be audited before training.
- Correct rows can still damage the decision boundary; cell-level causal import policy is required.

## Reconfirmed Dataset Judge / Junk Ranker Duties

The recovered judge/ranker must route rows by objective, not global good/bad status.

Known routes:

- `KEEP_STRUCTURED`
- `KEEP_BOUNDED_DECODER`
- `HOLD_LONG_OUTPUT`
- `USE_FOR_DENOISE_REPAIR`
- `USE_AS_NEGATIVE`
- `NEEDS_RETRIEVAL`
- `QUARANTINE_LABEL_CONFLICT`
- `DROP_DUPLICATE`
- `NEEDS_HUMAN_REVIEW`

Known risk signals:

- target over decoder budget,
- long blob,
- HTML/doc fragment,
- decoder target truncated,
- raw internal token in decoder target,
- raw text leak in structured objective,
- short/junk target,
- degenerate repetition,
- missing evidence but decode allowed,
- budget bad but decode allowed,
- ambiguous action label,
- surface role conflict,
- duplicate semantic key,
- split overlap,
- shortcut dominated feature,
- teacher/verifier disagreement.

## Reconfirmed Decoder Branch Details

The bounded decoder branch existed because same-harness evaluation showed:

```text
Gemma: 0.7815
harnessed product: 0.4121
standalone 100M: 0.0203
```

The standalone 100M failure was concrete:

- low standalone score,
- internal token leaks,
- short/junk behavior after suppression.

The non-hidden analog repair package was structurally clean:

```text
400 positive user-facing rows
100 internal-control negatives
100 counterfactual surface rows
100 short-output negatives
0 decoder internal rows
0 hidden-text rows
train/eval/strict: 524 / 88 / 88
```

But the early measured probe mixed impossible targets:

```text
truncated target rows: 47/96
target p95 about 27845 tokens/chars
max decoder tokens: 768
```

Budget-clean micro-overfit proved bounded learning was possible:

```text
train loss: 7.36 -> 1.91
eval loss: 2.98 -> 1.92
contentful rate: 1.0
short/junk: 0
```

Before deletion, the tiny bounded decoder CE probe had only shown:

```text
step 10 loss: 1.8922948837280273
```

That is not a capability proof.

## Reconfirmed Training Telemetry Requirements

Any future probe must emit, at minimum:

- `loss_by_step.jsonl`
- `eval_loss_by_checkpoint.jsonl`
- `row_token_loss.jsonl`
- `row_field_logits.jsonl`
- `row_field_losses.jsonl`
- `field_exact_by_split.json`
- `field_exact_by_cell.json`
- `confusion_matrix.json`
- `margin_confidence_entropy.jsonl`
- `high_confidence_wrong_rows.jsonl`
- `row_gradient_norms.jsonl`
- `sample_generation_audit.json`
- `short_output_probe.json`
- `repetition_probe.json`
- `internal_leak_probe.json`
- `module_delta_norms.json`
- `cleanup_proof.json`

Without these artifacts, the run is not a valid training signal.

## Recovered Stage-ID Clusters

The session scrape surfaced many older stage references, especially:

```text
2330, 6334, 4243, 4242, 4247, 3968, 4244, 4234,
4078, 3402, 6239, 5838, 4233, 4230, 6156, 4239,
2043, 4217, 2777, 4253, 5487, 5968, 6158, 6333,
2590, 5881, 6233, 6616, 6296, 5873, 5967, 5970,
6295, 6046
```

Interpretation:

- `2590`, `5967`, `5970`, `5881`, `5873`, and `6616` likely point to old policy/controller/route/sidecar training surfaces.
- `6239`, `6333`, `6334`, and `6295/6296` likely point to standalone/codegen/frontier curriculum work.
- `4242-4255` and nearby `423x` stages likely point to overlay/runtime/candidate-source ledger work.

These are recovery clues. They should drive future targeted script/session extraction, not training.

## Actionable Recovery Implications

1. Treat run ledgers as a missing source of truth.
2. Reconstruct policy/route training surfaces from old stage IDs before broad mining.
3. Restore candidate selector and behavior-value objectives from Stage8615 labels.
4. Keep the bounded decoder probe blocked until upstream structured surfaces and telemetry are ready.
5. Keep all runtime/body/source/Gemma/harness authority closed.

## Current Authority

Still closed:

- model execution,
- decoder CE training,
- runtime,
- source/body emission,
- Gemma,
- harness/scoring,
- controller merge,
- promotion.
