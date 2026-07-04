# Decoder Stage Deep Reconstruction

This file expands the decoder branch reconstruction.

## Why Decoder Was Reopened

Same-harness evaluation showed the standalone 100M path was the weak link.

Known metrics:

```text
Gemma: 0.7815
harnessed product: 0.4121
standalone 100M: 0.0203
```

Standalone failures were not abstract:

```text
low score
internal token leaks
short/junk behavior after suppression
```

This justified a bounded standalone decoder repair branch.

## Suppression Failure

Inference-time suppression reduced internal token leakage but caused:

```text
short outputs
junk outputs
empty outputs
```

Lesson:

```text
leak suppression must be paired with contentfulness and length behavior
```

## Non-Hidden Analog Repair Package

The decoder repair package used non-hidden analog data.

Composition:

```text
400 positive user-facing rows
100 internal-control negatives
100 counterfactual surface rows
100 short-output negatives
0 decoder internal rows
0 hidden-text rows
```

Split:

```text
train: 524
eval: 88
strict: 88
```

This was structurally clean but too broad for tiny learnability.

## Tiny Probe Learnability Issue

The early measured probe was too small and included impossible targets.

Problems:

```text
train rows: 64
eval rows: 16
strict rows: 16
batch size: 2
max steps: 8
row exposure: about 16 rows
p95/max target length: 27k-30k chars/tokens
max decoder tokens: 768
byte tokenizer
```

Long web/html/codegen rows were structurally mismatched to the decoder budget.

Lesson:

```text
Do not train tiny decoder probes on 30k-char targets with a 768-token budget.
```

## Budget-Clean Micro-Overfit

Budget-clean micro-overfit proved the model could learn bounded rows.

Known result:

```text
train loss: 7.36 -> 1.91
eval loss: 2.98 -> 1.92
contentful rate: 1.0
short/junk: 0
```

This showed the decoder itself was not hopeless.

## Remaining Generation Failures

Even after budget-clean learning, generation had:

```text
degenerate repetition
no counterfactual RETRIEVE_MORE
target prefix match 0
```

Interpretation:

```text
bounded CE can reduce loss
but decoder still needs structured gate and repair objectives
```

## Structured Decoder-State Split

Rows were split into:

```text
bounded decoder rows: 49
long-output holdout rows: 47
budget-bad rows: 47
html doc fragments: 15
```

This was the key correction:

```text
structured state first
bounded decoder second
```

## Bounded Decoder Argument Surface

The bounded decoder argument stage separated decision from rendering.

It had:

```text
rows: 144
decode_allowed: 96 true / 48 false
surface classes: 6 balanced
target argument losses: 0
decoder authorized rows: 0
```

Meaning:

```text
the compiler could identify bounded argument render surfaces without opening decoder CE yet
```

## Candidate Package Design

Stage8565 passed candidate package design audit.

Known metrics:

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

## Probe Wrapper And Loss Mask

Stage8566/8567 designed/audited the wrapper.

Stage8568/8569 designed/audited loss-mask reopen.

Final tiny selected rows:

```text
64 total
train: 32
eval: 16
strict_eval: 16
```

Language balance:

```text
python: 16
rust: 16
c_family: 16
web_js_ts_html: 16
```

Surface balance:

```text
MAINTAINER_EXPLANATION_ARGS: 16
REPAIR_PLAN_ARGS: 16
PATCH_HUNK_ARGS: 16
TEST_PLAN_ARGS: 16
```

Loss contract:

```text
future_losses_allowed: ["decoder_ce"]
future_losses_forbidden:
  structured_aux_ce
  denoise_ce
  runtime_reward
  preference_loss
  teacher_distill_loss
```

## Command Surface

The trainer command needed:

```text
--mode bounded_decoder_ce_probe
--manifest
--max-train-rows 32
--max-eval-rows 16
--max-strict-rows 16
--max-steps 16
--batch-size 2
--max-decoder-tokens 256
--decoder-ce-weight 1.0
--structured-aux-weight 0.0
--denoise-weight 0.0
--teacher-distill-weight 0.0
--require-loss-mask-enforcement-audit
--cleanup-checkpoints-after-probe
--no-final-checkpoint-export
--dry-run 0
--save-final-checkpoint 0
--skip-final-model-save 1
--export-browser-bitnet 0
```

Runtime:

```text
/home/peyton/miniconda3/envs/code_assist_runtime/bin/python
```

Bare `python` was invalid because it lacked `torch.nn`.

Also required:

```text
--repo-root /data/agentkernel-seq2seq-text-lab
```

## What The Probe Was Supposed To Answer

The tiny probe was not meant to prove final decoder capability.

It was meant to answer:

```text
does the trainer execute the bounded CE path safely?
does loss move?
is eval loss measured?
are artifacts clean?
are internal tokens absent?
are outputs contentful?
are outputs non-repetitive?
does cleanup retain no checkpoints?
```

## What It Actually Answered Before Deletion

Only:

```text
the command reached training
loss was computed
step 10 loss was 1.8922948837280273
```

Everything else remains unknown.

## Post-Recovery Decoder Next Step

After recovery and cleanup hardening, rerun the tiny bounded decoder CE probe.

Then immediately audit:

```text
training completed steps
loss_by_step
eval/strict loss
sample generations
contentful rate
short/junk rate
repetition rate
internal-token leak rate
EOS behavior
module delta norms
checkpoint cleanup proof
```

Only after that decide whether to:

```text
patch loss/EOS/target rendering
or widen bounded decoder rows
or add denoise repair objective
```

