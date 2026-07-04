# Objective Readiness Map

This document estimates how close the project was to the final objective before the deletion incident.

The final objective is:

```text
100M beats Gemma-12B on Python, Rust, C/C++, JS/HTML/TS
in standalone weights and full product harness,
with expert maintainer eval and anti-eval-hacking.
```

## Readiness Summary

The project was not close to final completion, but it was close to the first valid bounded decoder measurement.

Approximate state:

```text
control/curriculum substrate: strong
repo graph static objectives: seeded and audited
bounded decoder package: structurally ready
actual decoder capability: not yet proven
standalone > Gemma: not proven
product harness > Gemma: not proven
expert eval readiness: designed, not complete
scale readiness: conceptual, not executed
```

## Completed Or Mostly Completed

### Structured Policy Spine

Status: structurally strong.

Evidence:

```text
intent-to-build strategy cleaned of shortcuts
finite structured control solved exactly when balanced
deterministic budget/decode overlay removed false decode/budget allows
dataset judge/ranker exists conceptually and had stage support
```

Remaining:

```text
native 100M structured aux still weak on semantic field exactness
needs more contrastive rows and fusion
```

### Curriculum Compiler / Dataset Judge

Status: strong substrate.

Evidence:

```text
canonical graph obligations
counterfactual siblings
mixed replay
shortcut audits
junk/routing ranker
cell-level regression attribution
objective-aware row routing
```

Remaining:

```text
needs centralization into durable APIs
needs scale-path enforcement for 1M+ rows
```

### Repo Graph Maintenance Substrate

Status: seeded and structurally audited.

Evidence:

```text
repo_state_graph_v1 seed audit passed
symbol binding audit passed
edit localization audit passed
patch operator audit passed
verifier repair audit passed
bounded decoder argument audit passed
```

Remaining:

```text
small 144-row surfaces only
model training not yet proven for these objectives
needs scale-up and real repo evidence
```

### Bounded Decoder Candidate Package

Status: structurally ready.

Evidence:

```text
96 candidates
64 tiny probe rows
balanced languages and surfaces
target caps respected
loss masks decoder_ce-only
current authority closed before execution
```

Remaining:

```text
actual tiny probe quality not audited
cleanup unsafe
telemetry incomplete due deletion
```

## Not Yet Proven

### Decoder Capability

Status: not proven.

The tiny bounded decoder probe reached:

```text
step 10 loss: 1.8922948837280273
```

But this is not enough.

Missing:

```text
final train loss
eval loss
strict loss
row-token loss
sample generation audit
EOS/length audit
short/junk audit
repetition audit
leak audit
module delta norms
cleanup proof
```

### Standalone 100M > Gemma-12B

Status: not proven.

Earlier same-harness eval had:

```text
Gemma: 0.7815
harnessed product: 0.4121
standalone 100M: 0.0203
```

This is why the standalone decoder branch existed.

Before deletion, no new evidence showed standalone 100M beating Gemma.

### Full Product Harness > Gemma-12B

Status: not proven.

Harness/product route was still closed.

Needed:

```text
bounded decoder repair improves standalone
controlled harness integration
same-harness scoring
anti-cheat audit
Gemma comparison only after gates reopen
```

### Expert Maintainer Eval

Status: designed conceptually, not complete.

Needed eval tasks:

```text
intent -> build strategy
repo graph -> files/symbols
symbol use -> definitions/imports/tests
failure log -> root cause
root cause -> edit operator
operator -> bounded patch args
patch -> verifier expectation
verifier failure -> repair/abstain
```

### 1M+ Scale

Status: not ready for raw ingestion.

Needed:

```text
typed transition allocation
judge/ranker gates
counterfactual obligations
loss masks
objective-specific routing
anti-cheat checks
```

Do not scale raw Python files.

## How Close Were We?

A precise framing:

```text
We were not close to final v2.7 completion.
We were close to the first valid bounded decoder CE measurement.
```

Before deletion, the project had crossed from:

```text
design / static audit
```

to:

```text
first actual tiny bounded decoder training probe
```

That is an important threshold, but still early relative to beating Gemma.

## Remaining Milestones To Objective

### Milestone A: Restore And Harden

```text
restore repo
patch cleanup safety
recover docs/stages
rerun static audits
```

### Milestone B: Tiny Bounded Decoder Probe

```text
rerun 16-step probe
collect full telemetry
prove no leaks/repetition/short collapse
audit cleanup
```

### Milestone C: Bounded Decoder Improvement

```text
expand rows carefully
counterbalance graph topology
add EOS/length objectives if needed
add denoise repair objective
measure eval/strict improvement
```

### Milestone D: Standalone Repair

```text
run standalone eval
verify internal leak zero
verify contentful output
compare against prior 0.0203
iterate until meaningful score
```

### Milestone E: Same-Harness Reentry

```text
reopen controlled harness
score 100M standalone and product path
score Gemma same harness
check anti-cheat
```

### Milestone F: Multilingual Maintainer Eval

```text
Python
Rust
C/C++
JS/HTML/TS
expert maintainer tasks
repo graph / symbol / operator / verifier loop
```

### Milestone G: Beat Gemma

Only complete when:

```text
100M standalone > Gemma-12B
100M product harness > Gemma-12B
all target languages covered
anti-eval-hacking passes
runtime/source/body/promotion gates are justified
```

## Key Risk

The biggest remaining risk was decoder quality:

```text
the control spine had advanced
the decoder had not yet proven contentful safe generation
```

This is why the project was at the decoder stage.

