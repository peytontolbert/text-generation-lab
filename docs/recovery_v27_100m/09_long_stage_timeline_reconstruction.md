# Long Stage Timeline Reconstruction

This file reconstructs the important research arc across the late v2.7 run cluster.

It is not a byte-perfect stage registry. It is a high-signal memory of what the stages proved and why the project was at the bounded decoder point after 8400+ stages.

## Big Arc

The project moved through these phases:

```text
1. early transition/control and runtime boundaries
2. semantic/guard controller work
3. canonical curriculum graph and counterfactuals
4. trainability and semantic boundary work
5. same-harness product/standalone evaluation
6. standalone decoder repair branch
7. structured state / denoising turn
8. repo graph maintenance cognition spine
9. bounded decoder argument and CE probe branch
```

The project was not drifting. The late stages were narrowing the weak point:

```text
the standalone 100M decoder path
```

## Stage 7900s: Control And Guard Spine

The durable research spine around Stage7933 covered the early v2.7 control work.

Main idea:

```text
raw/task evidence
-> typed feature schema
-> transition/action label
-> guard/verifier decision
-> shadow controller replay
-> controller integration only after reliable control
```

Key lesson:

```text
Do not reopen decoder/source/body/runtime until the transition controller is reliable.
```

The system learned to treat software maintenance as transition prediction, not direct generation.

## Stage 8031 Area: Decoder Readiness Spine

Stage8031 was a decoder readiness spine refresh.

It was later insufficient because it only covered through Stage8030.

Important lesson from 8031-8060:

```text
transition coverage was not generic scale
```

The blocker was:

```text
split / authority / feature parity around rare TARGET_SHAPE transitions
```

Safe and unsafe import gaps were resolved through:

```text
exact-ledger authority
feature normalization
transition-family-specific coverage
```

Lesson:

```text
transition coverage must be proven per transition family, not inferred from row count.
```

## Stage 8112-8119: Canonical Curriculum Graph

The canonical curriculum graph became mandatory.

Every accepted row needed obligations:

```text
positive original
evidence removed
contradictory / unsafe twin
mixed replay
```

Stage8118 was a major milestone:

```text
expanded_mixed_rows: 10263
expanded_wrong_rows: 0
surface_family_count: 4
authority_true_rows: 0
```

Surface coverage:

```text
feature_normalized_guard: 2706
hard_negative_guard: 3435
safe_context_counterfactual: 330
scoped_standard_guard: 3792
```

Meaning:

```text
the compiler could prevent local isolated surface success
```

Not proven:

```text
the neural model learned the transition function
decoder readiness
controller merge
runtime/source/body emission
```

## Stage 8120-8125: Trainability Probe And Shortcut Detection

The canonical graph was structurally clean but trainability was not automatic.

Stage8120 found metadata/transition shortcuts dominated.

Stage8121 hydrated neutral evidence.

Stage8122 still did not beat metadata enough.

Lesson:

```text
neutralized evidence is not enough
evidence must produce lift over metadata baselines
```

## Stage 8126: Semantic Factorization Pivot

Local guard labels were too noisy.

Semantic labels worked better:

```text
SAFE
UNSAFE
RETRIEVE
```

Stage8126 metrics:

```text
eval_canonical_text_semantic_exact: 0.878
strict_canonical_text_semantic_exact: 0.859
eval_metadata_semantic_exact: 0.803
strict_metadata_semantic_exact: 0.766
```

Lesson:

```text
train semantic action first
render local guard labels separately
```

## Stage 8127-8136: Direct Boundary Evidence

Residual failures were mostly SAFE/UNSAFE polarity/sufficiency.

Stage8128 failed because boundary features were all zero:

```text
mean_safe_strength: 0.0
mean_unsafe_strength: 0.0
mean_evidence_sufficiency: 0.0
```

Stage8131 improved direct evidence coverage but still had:

```text
973 zero direct-evidence evidence-present rows
coverage about 75.4%
```

Key flaw:

```text
EVIDENCE_PRESENT != DECISION_SUFFICIENT_EVIDENCE
```

Stage8136 fixed this distinction:

```text
unresolved zero-direct rows: 0
patched rows: 79
insufficient direct evidence rows routed to retrieve: 894
direct-boundary evidence present rows: 3064
evidence-removed controls: 2543
```

Lesson:

```text
rows without decision-sufficient direct evidence must route RETRIEVE
```

## Stage 8137-8188: Semantic Lift, Boundary Geometry, Regression Attribution

Stage8137 showed patched direct-boundary features improved:

```text
strict semantic exact: 0.8856
lift over Stage8129 strict best: +0.0289
evidence-removed retrieve: 1.0
insufficient-direct retrieve: 1.0
```

Residuals remained:

```text
SAFE->UNSAFE
UNSAFE->SAFE
```

Stage8160 improved slightly:

```text
eval exact: 0.8825
strict exact: 0.8877
strict lift over Stage8137: +0.0021
beats metadata-with-status by +0.0331
```

But residual count stayed high.

Stage8169 found valid UNSAFE imports could distort shared rows:

```text
new imported rows accuracy: 1.0
shared rows regressed: 34
shared rows improved: 26
net shared improvement: -8
```

Lesson:

```text
correct rows are not automatically good training rows
cell-level weighting and regression attribution matter
```

Stage8172 found a non-regressing variant:

```text
keep_step4_external
eval exact: 0.88419
strict exact: 0.88834
```

Stage8185 improved after routing unsupported TARGET_SHAPE SAFE rows to retrieve:

```text
eval exact: 0.8865
strict exact: 0.8908
evidence-removed retrieve: 1.0
insufficient-direct retrieve: 1.0
contract route retrieve: 1.0
```

Stage8188 refused 393 surface-relaxed candidates due regression risk.

Lesson:

```text
same-surface import discipline matters
surface-relaxed rows can be correct but harmful
```

## Stage 8190-8200 Area: Cell-Level Causal Import Policy

Same-surface UNSAFE rows were individually correct but still damaged strict/shared behavior.

Important finding:

```text
import exact: 1.0
eval improved
strict regressed
shared regressed > shared improved
```

Missing policy:

```text
cell-level causal import policy
```

Each candidate cell should be:

```text
KEEP
PRUNE
LOWER_WEIGHT
FINE_ABLATION_ONLY
REQUEST_COUNTERBALANCE
```

This was a major dataset interpretability gain.

## Stage 8295-8325: Final Objective Gap And Same-Harness Evaluation

Stage8295 stated the final objective was incomplete.

Same-harness evaluation showed the weak link:

```text
Gemma: 0.7815
harnessed product: 0.4121
standalone 100M: 0.0203
```

Stage8325 found standalone failures were concrete:

```text
4/4 standalone rows had low score and internal token leaks
```

This drove the standalone decoder repair branch.

## Stage 8390-8408: Hidden References, Suppression Failure, Repair Package

Stage8390 confirmed hidden-reference materialization still leaked internal tokens.

Stage8392 showed inference-time suppression was not enough:

```text
leak reduced
but outputs became short/junk
```

Lesson:

```text
zero leak is insufficient if generation collapses
```

Stages8398-8401 built a non-hidden analog repair package:

```text
400 positive user-facing rows
100 internal-control negatives
100 counterfactual surface rows
100 short-output negatives
0 decoder internal rows
0 hidden-text rows
```

Stage8408 smoke passed:

```text
manifest load passed
runtime import smoke passed
trainer --help passed
aggregate passed
trainer execution attempted: false
trainer output dir created: false
train/eval/strict rows: 524 / 88 / 88
```

## Stage 8410-8427: Tiny Probe Plumbing And Learnability Card

Stage8410 caught the first dry-run design was too large:

```text
train cap 524
eval 88
steps 200
```

Stage8411 repaired to:

```text
train 64
eval 16
strict 16
max steps 16
```

Stage8426 measured probe generated empty output:

```text
generated chars: 0 for all rows
short/junk output rate: 1.0
positive contentful rate: 0.0
internal leak rows: 0
```

Stage8427 found the learnability issue:

```text
truncated target rows: 47/96
target p95 around 27845 tokens/chars
max decoder tokens: 768
row exposure only 25%
```

Lesson:

```text
target budget mismatch can masquerade as decoder failure
```

## Stage 8433-8440: Budget-Clean Micro Probe And Remaining Decoder Quality Failures

Stage8433 budget-clean micro-overfit worked:

```text
train loss: 7.36 -> 1.91
eval loss: 2.98 -> 1.92
contentful rate: 1.0
short/junk: 0
```

But later generation still had:

```text
degenerate repetition
no counterfactual RETRIEVE_MORE
target prefix match 0
```

Conclusion:

```text
bounded learning works
but free-form quality requires structured state and decoder gating
```

## Stage 8441-8459: Structured Decoder-State Turn

Stage8441 separated rows:

```text
bounded decoder rows: 49
long-output holdout rows: 47
budget-bad rows: 47
html doc fragments: 15
```

Stage8443/8444 built field-denoise objectives:

```text
576 objective rows
9 field targets
6 corruption types
no raw encoder/decoder text
authority rows: 0
```

Stage8445/8447 found baseline dominance:

```text
8/9 fields baseline-dominated
```

Stage8449 added harder non-shortcut rows:

```text
288 rows
hidden action rows: 96
hidden role rows: 96
masked action rows: 192
masked budget rows: 96
raw text rows: 0
```

Stage8455 first finite probe failed:

```text
train joint exact: 1.0
eval/strict joint exact: 0.84375
strict action exact: 1.0
strict decode_allowed exact: 0.9091
strict decoder_budget exact: 0.9091
```

Stage8459 balanced full-cell finite dry run passed:

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

Lesson:

```text
structured finite control is solvable and becomes the acceptance contract
```

## Stage 8464-8493: Native 100M Structured Aux And Deterministic Overlay

Stage8464 tensor schema existed:

```text
structured_feature_ids: [32, 29]
structured_field_mask: [32, 10]
structured_field_targets: [32, 10]
29 features
10 fields
153 cells
```

Stage8468 fixed unsupported label issue:

```text
9 trainable fields
retrieve_required derived
unbacked trainable fields: []
```

Stage8474 native probe was weak:

```text
strict joint exact: 0.354
strict action exact: 0.5
strict evidence exact: 0.625
retrieve false negatives: 36
false decode allows: 1
```

Stage8491 two-phase improved retrieve but regressed budget/decode false allows:

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

Stage8493 deterministic budget overlay passed:

```text
effective false budget OK rows: 0
effective false decode allow rows: 0
retrieve false negatives: 6
strict action exact: 0.625
strict evidence exact: 0.5
strict joint exact: 0.333
```

Lesson:

```text
learned heads are useful telemetry
hard safety gates use deterministic contracts
```

## Stage 8497-8507: Junk Ranker And Surface Confusion Repair

Stage8497/8498 created deterministic dataset junk/routing ranker.

It ranked 1875 rows:

```text
HOLD_LONG_OUTPUT: 955
KEEP_BOUNDED_DECODER: 115
KEEP_STRUCTURED: 466
NEEDS_RETRIEVAL: 2
USE_AS_NEGATIVE: 213
USE_FOR_DENOISE_REPAIR: 124
```

Risks found:

```text
target_over_decoder_budget: 955
long_blob: 703
html_doc_fragment: 261
raw_internal_token_in_decoder: 100
action_label_confusion_source: 213
surface_role_conflict_gap: 2
```

Stage8503 blocked surface-confusion training because shortcuts solved it:

```text
surface_marker_only exact: 1.0
requested_output_type_only exact: 1.0
strongest shortcut exact: 1.0
```

Stage8505-8507 fixed shortcuts enough:

```text
rows: 100
authority rows: 0
leak rows: 0
forbidden proxy feature rows: 0
old surface marker proxy exact: 0.0
old requested output type proxy exact: 0.0
strongest remaining single-feature baseline: 0.75
ceiling: 0.8
training blocked by shortcut audit: false
```

## Stage 8521-8529: Intent-To-Build Neutral Masked Objective

Stage8521 caught shortcut leakage:

```text
first_action exact: 1.0
plan_keyword exact: 1.0
allowed_import_count + available_repo_count exact: 1.0
direct target fields present: 144/144
```

Patch:

```text
neutral masked objective
corrupted_state + discriminating evidence -> recover clean build policy
```

Stage8529 was data-clean:

```text
rows: 144
build modes balanced: 48 / 48 / 48
languages balanced: 36 each
strongest single-feature baseline: 0.333
strongest combo-feature baseline: 0.333
import/repo count baseline: 0.333
authority rows: 0
decoder/runtime/body/Gemma closed
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

## Stage 8535-8565: Central Spine Refresh, Repo Graph, Bounded Decoder Package

Stage8535 refreshed central spine through 8534 and folded the model-stack doc back into the central spine.

Active hierarchy:

```text
structured policy
-> repo state graph
-> symbol binding
-> edit localization
-> patch operator
-> verifier repair
-> bounded decode
```

Stage8536-8539 built and audited repo_state_graph_v1 seed substrate.

Important fix:

```text
graph IDs no longer encode objective labels
objective metadata outside model input
edge endpoints resolve
authority closed
raw source/body/decoder/patch rows zero
```

Stage8543 symbol binding audit passed:

```text
rows: 144
label leaks: 0
endpoint failures: 0
strongest target baseline: 0.361
query_node_id target exact: 0.354
```

Stage8545 edit localization audit passed:

```text
rows: 144
label leaks: 0
endpoint failures: 0
strongest target baseline: 0.597
```

Stage8547 patch operator audit passed:

```text
rows: 144
label leaks: 0
endpoint failures: 0
strongest operator baseline: 0.639
strongest target baseline: 0.667
```

Stage8549 verifier repair audit passed:

```text
rows: 144
label leaks: 0
endpoint failures: 0
strongest action baseline: 0.743
strongest target baseline: 0.764
```

Stage8553 bounded decoder argument audit passed:

```text
rows: 144
decode_allowed: 96 true / 48 false
surface classes: 6 balanced
target argument losses: 0
decoder authorized rows: 0
```

Stage8565 bounded decoder CE candidate package design audit passed:

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

This is why the project was "just at the decoder stage": the control, graph, binding, localization, operator, repair, and bounded argument surfaces had passed static/structural audits.

## Stage 8566-8586: Tiny Bounded Decoder CE Probe Enablement

Stage8566-8583 moved from design to actual execution authorization.

Final tiny caps:

```text
train rows: 32
eval rows: 16
strict rows: 16
steps: 16
batch size: 2
max decoder tokens: 256
```

Stage8583 passed and authorized actual tiny probe execution.

Stage8584 first failed before training due missing explicit repo root.

Stage8585/8586 patched and audited repo root.

Retry then trained to at least step 10 before cleanup disaster.

