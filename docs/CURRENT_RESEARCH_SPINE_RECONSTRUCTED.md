# Current Research Spine Reconstructed

This spine reconstructs the active v2.7 100M model direction from available context after the workspace loss incident.

## Objective

Finish v2.7 so the 100M model can beat Gemma-12B on Python, Rust, C/C++, and JS/HTML/TS in both standalone and full product harness settings, including expert maintainer evaluation and anti-eval-hacking checks.

## Central Lesson

The project is not a raw codegen project.

The correct architecture is:

```text
safe control plane
-> structured software-state curriculum
-> repo graph and binding
-> edit/operator/verifier transitions
-> bounded decoder arguments
-> denoising repair
-> controlled harness
```

The decoder is one action inside a controlled software-maintenance loop, not the central authority.

## Active Hierarchy

```text
structured policy
-> repo state graph
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decoder
-> denoise repair
-> controlled harness
```

## Solved Or Hard Contracts

### Budget Safety Is Deterministic

Budget safety is a row fact, not learned authority.

Effective decode authorization must use deterministic facts:

```text
effective_decode_allowed =
    learned_decode_allowed
    AND deterministic_budget_ok
    AND deterministic_action_allows_decode
    AND deterministic_evidence_allows_decode
```

The learned budget head may be trained and measured, but it must not authorize decoding by itself.

### Long Output Is Holdout

Rows with target lengths beyond the active decoder budget are holdout rows, not decoder CE rows.

The prior failure mode was mixing 27k-30k character HTML/code targets with a 768-token byte-level decoder budget. That created false decoder failures and impossible training rows.

### Zero Leak Is Not Enough

Suppression-only fixes can eliminate internal token leaks by producing empty/short/junk output. Future decoder audits must require:

```text
internal_leak_rows == 0
contentful_output_rate above threshold
short_or_junk_rate == 0
degenerate_repetition_rate near 0
```

### Shortcut Dominance Blocks Training

If a single marker, requested output type, count feature, graph ID, node degree, or direct target field solves the task, training is blocked.

Shortcut audits must precede native probes.

### Decoder CE Stays Closed Until Gates Pass

Decoder CE may only reopen for tiny bounded probes with:

- authority-clean rows
- budget-clean rows
- loss-mask cards
- no hidden references
- no copied target text in model input
- telemetry artifacts
- checkpoint cleanup safety

## Important Stage Spine From Memory

### Stage8112-8119: Canonical Curriculum Graph

The compiler became a real curriculum graph, not isolated local surfaces.

Mandatory obligations:

- positive original
- evidence removed
- contradictory or unsafe twin
- mixed replay

Stage8118 passed expanded mixed replay:

```text
expanded_mixed_rows: 10263
expanded_wrong_rows: 0
surface_family_count: 4
authority_true_rows: 0
```

Lesson: every future mined/imported surface enters through counterfactual obligations, not raw mining.

### Stage8120-8136: Evidence Sufficiency And Direct Boundary Evidence

The trainability probe showed metadata/transition shortcuts dominated. Neutral evidence was not enough.

Stage8126 semantic factorization improved by collapsing local labels into:

```text
SAFE
UNSAFE
RETRIEVE
```

Stage8131 revealed:

```text
EVIDENCE_PRESENT != DECISION_SUFFICIENT_EVIDENCE
```

Stage8136 fixed zero-direct rows:

```text
unresolved_zero_direct_rows: 0
evidence_removed_controls_with_nonzero_features: 0
patched_rows: 79
insufficient_direct_evidence_rows_routed_to_retrieve: 894
direct_boundary_evidence_present_rows: 3064
```

Lesson: rows without direct decision evidence route to retrieve, not SAFE/UNSAFE training.

### Stage8137-8200: Semantic Lift, Polarity, And Import Policy

Patched direct-boundary features improved strict semantic exact, but residual polarity failures persisted.

Repeated lesson:

Correct imported rows can still damage shared boundary behavior.

This led to:

- pruning/reweighting
- shared-row regression attribution
- cell-level import policy
- same-surface-only discipline
- surface-relaxed candidates held out

### Stage8390-8427: Standalone Decoder Failure And Learnability Audit

Hidden-reference materialization leaked internal tokens. Inference-time suppression caused short/junk outputs.

Measured probe showed:

- internal token leak rows: 0
- generated chars: 0 for all rows
- short/junk output rate: 1.0
- positive contentful rate: 0.0

Learnability audit found severe target budget mismatch:

```text
truncated target rows: 47/96
target p95: about 27845 tokens/chars under byte-level tokenizer
max decoder tokens: 768
```

Lesson: do not interpret decoder failure until curriculum is budget-clean.

### Stage8433-8459: Budget-Clean Micro-Overfit And Structured State

Budget-clean micro-overfit worked:

```text
train loss: 7.36 -> 1.91
eval loss: 2.98 -> 1.92
contentful rate: 1.0
short/junk: 0
```

But generation still had semantic failures:

- degenerate repetition
- no counterfactual RETRIEVE_MORE
- target prefix match 0

Structured state split followed:

- field-denoise objectives
- harder non-shortcut rows
- finite structured control

Stage8459 passed balanced full-cell finite dry run:

```text
train/eval/strict rows: 192 / 48 / 48
joint train/eval/strict exact: 1.0 / 1.0 / 1.0
strict action exact: 1.0
strict decode_allowed exact: 1.0
strict decoder_budget_ok exact: 1.0
strict evidence_state exact: 1.0
false decode allows: 0
false budget OK: 0
weak cells: 0
```

Lesson: finite control is the contract; native 100M probes are implementation attempts against it.

### Stage8474-8493: Native Structured Aux Transfer Gap And Deterministic Overlay

Native 100M structured aux probes failed to reproduce finite control.

Stage8491:

```text
strict joint exact: 0.333
strict action exact: 0.625
strict decode_allowed exact: 0.75
strict budget exact: 0.9375
strict evidence exact: 0.5
retrieve false negatives: 6
false decode allows: 5
false budget OK: 5
```

Stage8493 fixed effective safety with deterministic overlay:

```text
effective false budget OK rows: 0
effective false decode allow rows: 0
retrieve false negatives: 6
```

Lesson: learned heads provide telemetry and proposals; hard safety remains deterministic.

### Stage8497-8504: Dataset Junk Ranker And Shortcut Loop

A deterministic dataset junk/routing ranker became necessary.

Stage8497 routed 1875 rows:

```text
HOLD_LONG_OUTPUT: 955
KEEP_BOUNDED_DECODER: 115
KEEP_STRUCTURED: 466
NEEDS_RETRIEVAL: 2
USE_AS_NEGATIVE: 213
USE_FOR_DENOISE_REPAIR: 124
```

Key risks:

```text
target_over_decoder_budget: 955
long_blob: 703
html_doc_fragment: 261
raw_internal_token_in_decoder: 100
action_label_confusion_source: 213
surface_role_conflict_gap: 2
```

Stage8503 blocked surface-confusion training because shortcuts solved it perfectly.

Stage8504 queued neutral evidence patching.

Lesson: closed-loop dataset judge -> curriculum repair -> probe -> attribution -> judge update is the correct operating cycle.

### Stage8505-8529: Intent-To-Build Strategy

Surface shortcut issue was fixed enough to proceed.

Stage8507:

```text
rows: 100
authority rows: 0
leak rows: 0
forbidden proxy feature rows: 0
old surface marker proxy exact: 0.0
old requested output type proxy exact: 0.0
strongest remaining single-feature baseline: 0.75
training blocked by shortcut audit: false
```

Stage8521 caught build-mode objective shortcuts:

```text
first_action exact: 1.0
plan_keyword exact: 1.0
allowed_import_count + available_repo_count exact: 1.0
direct target fields present: 144/144
```

Stage8529 repaired to clean model-ready structured objective:

```text
rows: 144
build modes balanced: 48 / 48 / 48
languages balanced: 36 each
strongest single baseline: 0.333
strongest combo baseline: 0.333
import/repo count baseline: 0.333
authority rows: 0
decoder/runtime/body/Gemma: closed
```

Trainable fields:

```text
build_mode
allowed_import_policy
blocked_import_policy
repo_dependency_policy
action_sequence
file_plan
```

Lesson: user intent -> build strategy is the first control spine, not code generation.

### Stage8535-8565: Repo Graph And Maintenance Cognition Spine

Central spine refresh folded model-stack work back into the existing spine.

Active hierarchy became:

```text
structured policy
-> repo state graph
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decode
```

Stage8539 passed repo-state graph seed audit after label-coded graph IDs were patched to opaque row-local IDs.

Then the repo-state graph spine filled in missing maintenance layers:

```text
8543 symbol binding audit after shortcut patch: passed
8545 edit localization audit: passed
8547 patch operator audit: passed
8549 verifier repair audit: passed
8553 bounded decoder argument audit after target patch: passed
8565 bounded decoder CE candidate package design audit: passed
```

Bounded decoder CE candidate package:

```text
candidate rows: 96
languages: 24 each
splits: 32 / 32 / 32
surfaces: 24 each
copied target text rows: 0
over cap rows: 0
current authority rows: 0
required telemetry artifacts: 8
```

Concern: graph topology baselines were approaching the ceiling in some objectives. Counterbalanced graph rows are needed so degree profiles do not become shortcuts.

### Stage8566-8586: Bounded Decoder CE Wrapper, Trainer Patch, And Retry Authorization

The bounded decoder CE path was structurally ready in concept.

Intended tiny probe:

```text
loss mask rows: 64
train/eval/strict: 32 / 16 / 16
languages: 16 each
surfaces: 16 each
non-decoder future loss rows: 0
unsafe loss mask rows: 0
over-cap rows: 0
forbidden command flags: 0
max steps: 16
```

Stage8580 failed correctly because the trainer entrypoint did not support the audited command surface.

Missing flags:

```text
--cleanup-checkpoints-after-probe
--decoder-ce-weight
--denoise-weight
--manifest
--max-strict-rows
--mode
--no-final-checkpoint-export
--require-loss-mask-enforcement-audit
--structured-aux-weight
```

Failed static checks:

```text
trainer_entrypoint_supports_required_flags: false
loss_mask_enforcement_runtime_assertions_available: false
artifact_cleanup_paths_writable: false
```

Archived session recovery shows the chain continued past Stage8580:

```text
8581 bounded decoder CE trainer command surface patch
8582 trainer command surface patch audit
8583 patched final pre-execution audit
8584 bounded decoder CE tiny probe execution outcome
8585 bounded decoder CE repo-root command patch
8586 repo-root command patch audit
```

Recovered Stage8586 registry state:

```text
latest_stage: 8586
latest_stage_name: stage8586_v27_bounded_decoder_ce_repo_root_command_patch_audit
latest_stage_next_best_step: Retry the tiny bounded decoder CE probe exactly once with the repo-root patched command.
latest_stage_passed_keys:
  - decoder_ce_training_authorized_next
  - model_execution_authorized_next
  - v27_bounded_decoder_ce_repo_root_command_patch_audit_passed
  - v27_bounded_decoder_ce_retry_tiny_probe_execution_authorized_next
registry_rows: 2264
stages_with_body_emission_authorized: 0
stages_with_gemma_authorized: 0
stages_with_runtime_authorized: 0
```

The retry command was bounded to the intended tiny measurement scope:

```text
--repo-root /data/agentkernel-seq2seq-text-lab
--mode bounded_decoder_ce_probe
--manifest stage8568...loss_mask_design.jsonl
--max-train-rows 32
--max-eval-rows 16
--max-strict-rows 16
--max-steps 16
--decoder-ce-weight 1.0
--structured-aux-weight 0.0
--denoise-weight 0.0
--require-loss-mask-enforcement-audit
--cleanup-checkpoints-after-probe
--no-final-checkpoint-export
--skip-final-model-save 1
```

At one recovered point, the live process was:

```text
pid: 901894
elapsed: 01:37
command: train_agentkernel_lite_encdec.py --mode bounded_decoder_ce_probe
output_dir: /data/agentkernel-seq2seq-text-lab/runs/local/probes/stage8584_v27_bounded_decoder_ce_tiny_probe_execution
```

Required post-run checks were supposed to include:

```text
exit code == 0
loss_by_step exists
eval_loss_by_checkpoint exists
row_token_loss exists
sample generation audit exists
short-output probe exists
internal leak probe exists
module_delta_norms exists
cleanup proof exists
no final checkpoint export
no runtime/body/source/Gemma/harness artifacts
```

### Stage8587: Workspace Loss Incident

During/after the tiny bounded decoder CE branch, an unsafe cleanup deleted the workspace.

Archived session recovery indicates the probe process exited, but the result was not a normal completed probe. The workspace appeared empty:

```text
/data/agentkernel-seq2seq-text-lab contained only . and ..
```

Missing after the incident:

```text
scripts/build_stage7678_v27_stage_registry.py
runs/summaries
runs/local/probes/stage8584_v27_bounded_decoder_ce_tiny_probe_execution
Stage8586 summary
Stage8584 probe output
.git
```

Searches of `/data` and `/data/tmp` did not find the lost seq2seq project artifacts.

The likely failure class was cleanup or output handling targeting the repo root or an incorrectly resolved parent path.

The probe result is invalid/unavailable as a durable promotion signal because the workspace, artifacts, and safety proofs were destroyed.

Primary recovery rule: no training resumes until safe cleanup and registry are rebuilt and tested.

## Current Status After Incident

We were not at final objective completion.

We were at the first bounded decoder measurement stage, after rebuilding the control spine and maintenance cognition spine. Stage8586 authorized exactly one tiny retry, but the retry outcome was invalidated by workspace loss.

What was structurally complete:

- canonical curriculum graph rule
- dataset judge/junk ranker
- deterministic budget/decode overlay
- intent-to-build objective
- repo_state_graph_v1 seed
- symbol binding objective
- edit localization objective
- patch operator objective
- verifier repair objective
- bounded decoder argument objective
- bounded decoder CE candidate package design

What was still missing:

- safe trainer command surface implementation
- safe cleanup utilities/tests
- actual valid tiny bounded decoder CE execution with retained telemetry
- denoise repair objective
- controlled maintainer loop
- harness/product integration
- Gemma comparison reopening
- runtime/body/source authority
- scale to 1M under judge

## Next Valid Move

Rebuild safety first:

```text
scripts/safe_paths.py
scripts/safe_cleanup.py
tests/test_safe_cleanup.py
scripts/build_stage7678_v27_stage_registry.py
```

Then reconstruct stage summaries and non-executing audits before any model execution.



## Stage8640-8642 Pipeline Recovery Update

Current registry frontier after this recovery pass: `stage8642_structured_aux_runtime_contract`.

Recovered pipeline pieces:

- The recovered transformer/rotary module remains the architectural target for the 100M maintainer path.
- The safe trainer command surface now carries `--implementation scaffold|transformer`.
- The gated runtime path now receives the selected implementation instead of silently falling back to the scaffold.
- A tiny recovered-transformer runtime path exists for future explicitly authorized probes; full 100M target execution remains closed.
- The exact 1506-vocab `agentkernel_bytelevel_bpe_v1` tokenizer was recovered as a stable pointer in `configs/tokenizer/agentkernel_bpe_1506_recovered_pointer.json`.
- The trainer now exposes `--tokenizer-json` and `--tokenizer-config`, records tokenizer choice in contract artifacts, and passes tokenizer selection into the batcher.
- The batcher can load the recovered AgentKernel BPE tokenizer through `tokenizers.Tokenizer.from_file`; byte fallback remains only for tiny recovery probes unless explicitly audited.
- A structured auxiliary probe loop now exists behind the same explicit execution gate as bounded decoder CE. It supports structured-head losses for the recovered policy/objective fields and writes field-level telemetry.
- Stage8641 proved, without execution, that the trainer accepts `transformer + recovered BPE tokenizer` for the bounded decoder CE contract.
- Stage8642 proved, without execution, that the trainer accepts `transformer + recovered BPE tokenizer` for the structured policy contract with decoder CE disabled.

Still not training-ready:

- `ready_for_100m_training` remains false.
- Model execution remains unauthorized.
- Decoder CE training remains unauthorized.
- Runtime/source/body/Gemma/harness/scoring/controller/promotion remain closed.
- The structured loop is restored as a tiny probe path, not yet a full target-config training path.
- Full tokenizer hash enforcement and local materialization policy still need to be hardened.
- Generation quality telemetry remains placeholder until an explicitly authorized measured generation probe exists.
- Row-token CE telemetry still needs full per-token loss maps before decoder widening.
- Reconstructed objective manifests are pipeline recovery surfaces, not final mined data.

Current rule:

Do not recover/mine datasets yet. Finish the training-plane contracts first: tokenizer hash gate, label-vocab cards, structured telemetry assertions, full target-config compatibility audit, and non-destructive runtime safety checks.

## Stage8653 Focused Storage And Single Cleanup Contract

Stage8653 adds a hard storage/control-plane rule after the workspace-loss incident: new JSON, stage summaries, artifacts, probe outputs, configs, docs, tests, and scripts must stay in focused repository locations rather than ad hoc paths. The canonical policy is `configs/storage/focused_storage_policy_v1.json`, and future stage builders should use `scripts/artifact_paths.py` for summary, artifact, probe, config, and doc paths.

The single cleanup entrypoint is `scripts/safe_cleanup.py`, backed by `scripts/safe_paths.py`. No additional cleanup scripts are allowed by policy. Cleanup scope remains checkpoint children only under a marked probe output directory with a matching run id. `/arxiv` is explicitly backup/source-of-truth storage: recovery reads and explicit backups are allowed, but cleanup, deletion, and training outputs there are forbidden.

Stage8653 passed with `storage_and_cleanup_tests_pass=true`, `single_cleanup_entrypoint=true`, `no_extra_cleanup_scripts=true`, `arxiv_backup_only=true`, and `arxiv_forbidden_cleanup_target=true`. No model execution, decoder CE, runtime, Gemma, harness, scoring, controller merge, or promotion authority was opened.

