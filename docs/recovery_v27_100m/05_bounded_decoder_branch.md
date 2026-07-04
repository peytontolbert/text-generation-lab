# Bounded Decoder CE Branch

This document reconstructs the bounded decoder CE branch state before deletion.

## Why This Branch Exists

Earlier decoder probes failed because the model was asked to decode before it reliably knew:

```text
surface
role
evidence state
action
budget
retrieve/decode decision
```

Failures included:

```text
empty outputs
short/junk outputs
degenerate repetition
missing RETRIEVE_MORE counterfactual behavior
long target budget mismatch
```

Budget-clean micro-overfit proved bounded targets can be learned.

Therefore the branch moved to:

```text
structured gate -> bounded decoder arguments -> tiny CE probe
```

## Candidate Package

Bounded decoder candidate package properties:

```text
candidate rows: 96
languages: balanced
surfaces: balanced
copied target text rows: 0
over-cap rows: 0
current authority rows: 0
```

## Loss-Mask Selection

Selected tiny probe rows:

```text
64 rows
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
```

Allowed future loss:

```text
decoder_ce only
```

Forbidden future losses:

```text
structured_aux_ce
denoise_ce
runtime_reward
preference_loss
teacher_distill_loss
```

Current authority before execution:

```text
training_authorized_now: false
model_execution_authorized_now: false
checkpoint_write_authorized_now: false
runtime_harness_authorized_now: false
gemma_authorized_now: false
scoring_authorized_now: false
source_body_authorized_now: false
decoder_ce_enabled_now: false
```

## Tiny Probe Settings

Audited settings:

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
dry-run: 0
save final checkpoint: 0
skip final model save: 1
export browser bitnet: 0
```

Correct runtime:

```text
/home/peyton/miniconda3/envs/code_assist_runtime/bin/python
```

Workspace repo root must be explicit:

```text
--repo-root /data/agentkernel-seq2seq-text-lab
```

## Required Telemetry

A valid probe must emit:

```text
loss_by_step
eval_loss_by_checkpoint
row_token_loss
EOS/length audit
short-output audit
repetition audit
leak audit
sample generation audit
module delta norms
failure buckets
cleanup proof
```

## Known Probe Output Before Deletion

The retried probe emitted:

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

This proves only that training started and loss was being computed.

It does not prove quality.

## Cleanup Guard Required Before Rerun

Do not rerun with cleanup enabled until cleanup is hardened.

Safe cleanup requirements:

```text
checkpoint_dir is absolute
checkpoint_dir exists
checkpoint_dir.name == "checkpoints"
checkpoint_dir is inside output_dir
checkpoint_dir != output_dir
checkpoint_dir != repo root
checkpoint_dir != "."
checkpoint_dir != "/"
checkpoint_dir is not a symlink escaping output_dir
```

If any check fails, abort before deletion.

## Next Valid Branch Step After Recovery

```text
1. Restore repo.
2. Patch cleanup safety.
3. Rebuild/recover bounded decoder stage artifacts.
4. Re-audit command.
5. Rerun tiny probe.
6. Audit telemetry.
7. Expand only if evidence supports it.
```

