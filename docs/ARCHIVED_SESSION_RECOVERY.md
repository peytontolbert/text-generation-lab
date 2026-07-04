# Archived Session Recovery

This file records facts recovered from `~/.codex/sessions` after the workspace loss incident.

There was no `~/.codex/archived_sessions` directory on this machine. The available source was:

```text
~/.codex/sessions
```

Relevant session logs found:

```text
/home/peyton/.codex/sessions/2026/06/28/rollout-2026-06-28T17-09-03-019f0f34-bf9b-76f2-885c-1da068412cfd.jsonl
/home/peyton/.codex/sessions/2026/06/28/rollout-2026-06-28T17-09-02-019f0f34-bdb2-7c93-ba8f-92e8f0fc1e5c.jsonl
/home/peyton/.codex/sessions/2026/06/24/rollout-2026-06-24T21-58-37-019efba4-6b90-73a0-a409-52ac2948636c.jsonl
```

## Recovered Late Frontier

The latest known registry frontier before the workspace loss was Stage8586:

```text
latest_stage: 8586
latest_stage_name: stage8586_v27_bounded_decoder_ce_repo_root_command_patch_audit
latest_stage_next_best_step: Retry the tiny bounded decoder CE probe exactly once with the repo-root patched command.
registry_rows: 2264
```

Authorization state recovered from registry:

```text
model_execution_authorized_next: true
decoder_ce_training_authorized_next: true
body_emission_authorized: 0 stages
runtime_authorized: 0 stages
gemma_authorized: 0 stages
```

Important: the model/decoder authorization was only for the tiny bounded decoder CE retry. It was not general training, runtime, body/source emission, Gemma, harness, scoring, controller merge, or promotion.

## Recovered Stage8580-8586 Chain

```text
stage8580_v27_bounded_decoder_ce_final_pre_execution_audit
stage8581_v27_bounded_decoder_ce_trainer_command_surface_patch
stage8582_v27_bounded_decoder_ce_trainer_command_surface_patch_audit
stage8583_v27_bounded_decoder_ce_patched_final_pre_execution_audit
stage8584_v27_bounded_decoder_ce_tiny_probe_execution_outcome
stage8585_v27_bounded_decoder_ce_repo_root_command_patch
stage8586_v27_bounded_decoder_ce_repo_root_command_patch_audit
```

Stage8580 had failed because the trainer did not support the audited command surface. Stage8581-8583 patched/audited that. Stage8585-8586 patched/audited the repo-root command and authorized exactly one retry.

## Recovered Tiny Probe Command Scope

The retry command included:

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

The live process was observed as:

```text
pid: 901894
elapsed: 01:37
command: train_agentkernel_lite_encdec.py --mode bounded_decoder_ce_probe
output_dir: /data/agentkernel-seq2seq-text-lab/runs/local/probes/stage8584_v27_bounded_decoder_ce_tiny_probe_execution
```

Required post-run checks were supposed to be:

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

## Incident Recovery

After the probe process exited, the result was not a normal completed probe.

Critical recovered finding:

```text
/data/agentkernel-seq2seq-text-lab was empty
```

It contained only:

```text
.
..
```

Missing:

```text
scripts/build_stage7678_v27_stage_registry.py
runs/summaries
runs/local/probes/stage8584_v27_bounded_decoder_ce_tiny_probe_execution
Stage8586 summary
Stage8584 probe output
.git
```

Searches did not recover seq2seq project artifacts from:

```text
/data
/data/tmp
```

Likely failure class:

```text
destructive cleanup or path-resolution bug
```

The retried command used both:

```text
--repo-root /data/agentkernel-seq2seq-text-lab
--cleanup-checkpoints-after-probe
--output-dir /data/agentkernel-seq2seq-text-lab/runs/local/probes/stage8584...
```

The suspected bug is that cleanup or output handling targeted the repo root or an incorrectly resolved parent path.

## Hard Recovery Rule

No further training or probe execution is authorized until:

```text
safe cleanup utilities exist
cleanup tests prove repo-root deletion is impossible
stage registry is rebuilt
loss-mask enforcement audit passes
final pre-execution audit passes
```
