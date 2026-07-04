# v2.7 100M Software Maintainer Research Recovery Notes

This file records the important research state for the local 100M model after the workspace deletion incident.

## Incident

The active workspace was:

```text
/data/agentkernel-seq2seq-text-lab
```

The repository contents were deleted by unsafe cleanup code added during the bounded decoder CE probe path.

The unsafe pattern was:

```python
checkpoint_dir = Path(str(manifest.get("training_summary", {}).get("checkpoint_dir", "") or ""))
if checkpoint_dir.exists():
    shutil.rmtree(checkpoint_dir)
```

When `checkpoint_dir` resolved to `Path("")`, it became `.` and deleted the workspace contents.

Never use this cleanup pattern again.

Safe cleanup must require:

```text
path is absolute
path exists
path name == "checkpoints"
path is inside output_dir
path != output_dir
path != repo root
path != "."
path != "/"
path is not a symlink escaping output_dir
```

Fail closed otherwise.

## Final Objective

Finish v2.7 so the local 100M model beats Gemma-12B on multiple languages:

```text
Python
Rust
C/C++
JavaScript/HTML/TypeScript
```

The model must beat Gemma-12B in:

```text
standalone weights
full product harness
```

The eval must include:

```text
expert-level maintainer evaluation
anti-eval-hacking checks
hidden-reference leakage checks
shortcut baseline checks
standalone and harnessed product comparison
```

## Core Research Thesis

Do not train the 100M as raw free-form codegen first.

The correct spine is:

```text
structured software state
-> safe transition/action policy
-> repo graph grounding
-> bounded decoder
-> verifier-guided repair
-> product/harness integration
```

The decoder is only one action inside a controlled software-maintenance loop.

The model should learn:

```text
repo/task/evidence state
-> classify surface
-> choose safe action
-> decide retrieve/correct/copy/build
-> maybe decode bounded output
-> verify
-> repair
```

Not:

```text
prompt -> free-form code
```

## Active Research Spine

The durable spine before deletion was:

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

## Model Stack

The intended system is a multi-model / multi-head software maintenance stack:

```text
SSM/Mamba          -> repo-wide compression and long logs
GNN                -> repo structure, call graph, dependency graph
encoder/retriever  -> evidence ranking and grounding
encoder-decoder    -> state transitions and bounded output
decoder            -> bounded candidates only
denoiser/diffusion -> repair malformed/short/leaky/failed outputs
linear/MLP heads   -> gates, rankers, confidence, OOD
symbolic tools     -> AST, tests, compiler, static checks
verifiers          -> authority and acceptance
```

Do not force one 100M seq2seq model to infer everything alone.

## Dataset Judge / Curriculum Compiler Law

Every row must have a compiler-visible reason and route.

Known routes:

```text
KEEP_STRUCTURED
KEEP_BOUNDED_DECODER
HOLD_LONG_OUTPUT
USE_FOR_DENOISE_REPAIR
USE_AS_NEGATIVE
NEEDS_RETRIEVAL
QUARANTINE_LABEL_CONFLICT
DROP_DUPLICATE
```

A row can be valid for one objective and unsafe for another.

Example:

```text
long HTML row:
  bad for decoder CE
  good for long-output holdout
  good for budget classifier
```

## Hard Contracts

### Budget Safety

Budget safety is deterministic, not learned authority.

Effective decode authorization should be:

```text
effective_decode_allowed =
  learned_decode_allowed
  AND deterministic_budget_ok
  AND action_allows_decode
  AND evidence_allows_decode
  AND junk_ranker_route allows decode
```

### Long Output

Long outputs are holdout unless chunked.

Rows above decoder budget must not enter decoder CE.

### Leak Suppression

Zero internal-token leak is not enough.

Future decoder audits must also require:

```text
internal_leak_rows == 0
short_or_junk_rate == 0
degenerate_repetition_rate near 0
contentful_output_rate high
```

### Shortcut Blocking

Shortcut dominance blocks training.

If a single feature or simple proxy solves the task, do not train.

### Authority

Decoder CE stays closed until structured gates pass.

Runtime/source/body/Gemma/harness/scoring stay closed unless explicitly authorized by a stage gate.

## Decoder Failure Lessons

Flat decoder failed for structural reasons:

```text
empty outputs
degenerate repetition
missing counterfactual RETRIEVE_MORE behavior
long target truncation
target p95 around 27k-30k chars while decoder budget was 768 byte tokens
```

Conclusion:

```text
raw decoder failure != model cannot learn
raw decoder failure = curriculum/gating problem
```

Budget-clean micro-overfit did work:

```text
train loss dropped strongly
eval loss dropped
contentful output rate reached 1.0
short/junk dropped to 0
```

Bounded decoding is learnable if rows are budget-safe and clean.

## Structured-State Layer

Structured fields included:

```text
action_label
decoder_budget_ok
decode_allowed
evidence_state
language_group
repair_role
repair_surface
surface_role
target_length_bucket
```

`retrieve_required` became derived/inactive because it had no direct labels.

Finite structured control passed when balanced:

```text
joint train/eval/strict exact: 1.0
action exact: 1.0
decode_allowed exact: 1.0
budget exact: 1.0
evidence exact: 1.0
false decode allows: 0
false budget OK: 0
```

Native 100M aux was weaker:

```text
strict joint around 0.33
action around 0.625
evidence around 0.5
decode/budget false allows existed until deterministic overlay
```

Important interpretation:

```text
finite control is the spec
100M probes are implementation attempts against that spec
```

## Intent-To-Build Strategy

Structured policy target:

```text
user intent
-> build strategy
-> allowed imports/repos/tools
-> file/action plan
-> verify/repair
```

Build modes:

```text
USE_WHITELIST_IMPORT
BUILD_ON_TOP
BUILD_FROM_SCRATCH
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

Shortcut repair lesson:

Stage8521-style failure showed labels leaked through:

```text
first_action
plan_keyword
allowed_import_count + available_repo_count
direct target fields
```

Patch required neutral masked objective:

```text
corrupted_state + discriminating evidence
-> recover clean build policy
```

No visible target fields.

## Repo-State Graph Spine

The model needs maintenance cognition beyond build strategy:

```text
repo_state_graph_v1
symbol binding
edit localization
patch operator
verifier repair
bounded decoder arguments
```

Graph anti-cheat rules:

```text
node IDs must be opaque
graph IDs must not encode labels
objective metadata stays outside model input
edge endpoints must resolve
raw source/body/patch rows remain closed unless authorized
```

## Symbol Binding

Target transition:

```text
repo_state_graph packet
+ visible symbol/import/callsite/test/failure evidence
-> binding decision
```

Labels:

```text
BIND_CALL_TO_SYMBOL
BIND_IMPORT_TO_MODULE
BIND_TEST_TO_SYMBOL
BIND_FAILURE_TO_SYMBOL
RETRIEVE_MORE
ABSTAIN_UNBOUND
```

Binding-specific shortcut checks:

```text
query_node_id alone must not solve target_node_id
node degree / edge type count alone must not solve binding_action
```

## Edit Localization

The model must learn:

```text
intent + repo graph + failure/evidence
-> target file
-> target symbol
-> edit region
-> test target
```

Needed fields:

```text
target_file_policy
target_symbol_policy
edit_region_policy
test_target_policy
```

## Patch Operator Algebra

Do not jump directly to code text.

Predict edit operators first:

```text
INSERT_FUNCTION
REPLACE_EXPR
WRAP_CALL
ADD_IMPORT
CHANGE_CONDITION
ADD_TEST_CASE
UPDATE_CONFIG_FIELD
CREATE_FILE
```

Transition:

```text
intent/repo/evidence -> edit_operator + arguments
```

Then bounded decoder renders arguments/text.

## Verifier Repair

Verification is not just a gate. It is a learned transition.

Needed fields:

```text
verification_command
expected_pass_condition
failure_type
repair_operator
rollback_or_continue
```

Episode format:

```json
{
  "observe": "...",
  "orient": "...",
  "act": "...",
  "verify": "...",
  "failure": "...",
  "repair": "...",
  "final_state": "..."
}
```

## Denoising / Diffusion Role

Diffusion/denoising should not be the primary "write code from scratch" engine.

Best role:

```text
bad output/patch + verifier failure + target state
-> repaired output/patch/state
```

Use denoising across the loop:

```text
observe denoiser:
  raw task/log/context -> clean structured observation

orient denoiser:
  masked state -> evidence/action/budget/decode fields

act denoiser:
  bad action trace -> legal action sequence

decode denoiser:
  short/leaky/repetitive output -> clean bounded output

patch denoiser:
  bad patch + verifier failure -> repaired patch

verify denoiser:
  noisy test/log output -> normalized failure state
```

## Bounded Decoder CE Branch

Candidate package before deletion:

```text
96 candidate rows
balanced languages
balanced surfaces
copied target text rows: 0
over-cap rows: 0
current authority rows: 0
```

Loss-mask branch:

```text
64 selected rows
train/eval/strict: 32 / 16 / 16
languages: 16 each
  python
  rust
  c_family
  web_js_ts_html
surfaces: 16 each
  MAINTAINER_EXPLANATION_ARGS
  REPAIR_PLAN_ARGS
  PATCH_HUNK_ARGS
  TEST_PLAN_ARGS
future losses allowed: only decoder_ce
current training/model/checkpoint authority false before execution
over-cap rows: 0
unsafe rows: 0
```

Probe settings:

```text
max train rows: 32
max eval rows: 16
max strict rows: 16
max steps: 16
batch size: 2
max decoder tokens: 256
decoder CE weight: 1.0
structured aux weight: 0.0
denoise weight: 0.0
teacher distill weight: 0.0
```

Correct runtime Python:

```text
/home/peyton/miniconda3/envs/code_assist_runtime/bin/python
```

Bare `python` was wrong:

```text
/home/peyton/miniconda3/bin/python
```

It lacked `torch.nn`.

## Probe Result Before Deletion

The tiny probe reached training and emitted:

```json
{
  "step": 10,
  "loss": 1.8922948837280273,
  "lr": 0.0002,
  "pcgrad_conflicts": 0,
  "pcgrad_min_cosine": 0.0,
  "pcgrad_snapshots": 0
}
```

Then unsafe cleanup deleted the workspace.

Interpretation:

```text
model execution started
training progressed at least to step 10
no final quality audit exists
no valid conclusion about decoder repair quality can be made
```

## Required Bounded Probe Telemetry

A valid bounded decoder CE probe must emit:

```text
loss_by_step
eval_loss_by_checkpoint
row_token_loss
EOS/length audit
short-output audit
repetition audit
leak audit
sample_generation audit
module delta norms
failure buckets
cleanup proof
```

Must verify:

```text
checkpoint cleanup safe
no final checkpoint export
no hidden refs
no Gemma
no harness scoring
no runtime/source/body emission
```

## Evaluation Philosophy

Do not claim model learning from compiler/shadow replay.

Important distinction:

```text
compiler can label rows
!=
model learned transition function
```

Training readiness requires:

```text
beats metadata shortcut baselines
counterfactual flip accuracy
evidence-removed -> retrieve
no high-confidence wrong accepts
per-surface exact
per-obligation exact
no collapse
no leakage
```

## Expert Maintainer Eval

The final 100M eval should test:

```text
intent -> build strategy
repo graph -> relevant files/symbols
symbol use -> definition/import/test relation
failure log -> root cause class
root cause -> edit operator
edit operator -> bounded patch args
patch -> verifier expectation
verifier failure -> repair/abstain
```

Not just final text similarity.

## Anti-Eval-Hacking Requirements

Every eval should check:

```text
no hidden-reference materialization
no target text in input
no label-coded IDs
no surface marker shortcut
no requested-output-type shortcut
no duplicate semantic key leakage
no split overlap
no raw source/body leakage unless intended
no long target truncation
no metadata-only baseline dominance
no graph-degree-only baseline dominance
no verifier result leakage
no Gemma teacher text treated as ground truth
```

## Scaling Plan

Do not scale raw Python files.

Scale by transition type:

```text
150k intent/build strategy
150k repo graph / symbol binding
150k edit localization
150k patch operator
150k verifier/failure diagnosis
150k repair/denoise episodes
100k abstain/retrieve/missing evidence
100k bounded rendering
```

Every scaled row must pass:

```text
canonical schema
dataset judge route
loss mask
counterfactual sibling where applicable
no leakage
no shortcut dominance
split safety
objective-specific route
```

## Latest Known Stages Before Deletion

Known chain:

```text
8566 wrapper design
8567 wrapper audit
8568 decoder CE loss-mask reopen design
8569 loss-mask reopen audit
8570 trainer command static design
8571 trainer command static audit
8572 artifact retention cleanup contract
8573 cleanup contract audit
8574 execution enablement design
8575 enablement design audit
8576 execution authorization review card
8577 review card audit
8578 tiny probe execution manifest
8579 execution manifest audit
8580 final pre-execution audit
8581 trainer command surface patch
8582 trainer command surface patch audit
8583 patched final pre-execution audit
8584 failed execution outcome
8585 repo-root command patch
8586 repo-root command patch audit
```

Stage8583 passed and authorized the tiny bounded decoder CE probe.

Stage8584 first failed pre-training due missing explicit `--repo-root`.

Stage8585/8586 patched and audited explicit repo root.

Retry then started training and emitted step-10 loss before unsafe cleanup deleted the workspace.

## Recovery Sources Found

Possible local recovery sources:

```text
/data/agentkernel/scripts/train_agentkernel_lite_encdec.py
/data/agent_kernel_lite/scripts/train_agentkernel_lite_encdec.py
/data/transformer_10/scripts/agent_kernel_lite/train_agentkernel_lite_encdec.py
```

Potential directories:

```text
/data/agentkernel
/data/agent_kernel_lite
/data/transformer_10
/data/tmp
/tmp
```

## Resume Plan After Restore

After restoring the repo:

```text
1. Patch cleanup safely before any run.
2. Recreate/recover stages through 8583 if needed.
3. Record Stage8584 failure if missing.
4. Ensure repo-root command patch exists.
5. Re-audit tiny bounded decoder CE command.
6. Rerun tiny probe only after cleanup guard is proven safe.
7. Audit telemetry before any expansion.
```

## Bottom Line

The winning 100M path is:

```text
structured transition control first
repo graph grounding second
bounded decode third
verifier-guided denoising repair fourth
scale only judged rows fifth
```

The 100M model should become a controlled software-maintenance transition system, not a small model forced to hallucinate full code from prompts.
