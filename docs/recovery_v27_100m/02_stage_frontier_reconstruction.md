# Stage Frontier Reconstruction

This file reconstructs the late-stage frontier from memory and terminal outputs.

## Latest Known Safe Frontier Before Execution

Stage8583 passed:

```text
stage8583_v27_bounded_decoder_ce_patched_final_pre_execution_audit
```

It authorized one tiny bounded decoder CE probe execution.

It did not authorize:

- Gemma
- harness/scoring
- runtime
- source/body emission
- promotion

## Known Chain

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

## Stage8580 Initial Failure

Stage8580 initially failed because the trainer did not support the audited command surface.

Missing flags were:

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

This was a good failure. The blocker was trainer interface/runtime safety contract mismatch, not dataset structure.

## Stage8581-8583 Patch

The trainer was patched to support the bounded decoder CE probe surface.

Important additions:

- `--mode bounded_decoder_ce_probe`
- `--manifest`
- `--max-strict-rows`
- `--decoder-ce-weight`
- `--structured-aux-weight`
- `--denoise-weight`
- `--require-loss-mask-enforcement-audit`
- `--cleanup-checkpoints-after-probe`
- `--no-final-checkpoint-export`

The patched command also used:

```text
/home/peyton/miniconda3/envs/code_assist_runtime/bin/python
```

instead of bare `python`, because bare `python` lacked `torch.nn`.

## Stage8584 First Execution Attempt

The first authorized execution attempt failed before training because the command lacked explicit `--repo-root`.

Bad resolution:

```text
/data/agentkernel-seq2seq-text-lab/legacy_src/runs/local/artifacts/...
```

Expected:

```text
/data/agentkernel-seq2seq-text-lab/runs/local/artifacts/...
```

No probe artifacts were created by that first attempt.

## Stage8585-8586 Patch

The command was patched to include:

```text
--repo-root /data/agentkernel-seq2seq-text-lab
```

Stage8586 passed and authorized one retry.

## Retried Probe Result

The retried tiny probe started actual training and emitted:

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

Then cleanup attempted to remove `.` and deleted the workspace.

## Interpretation

The run proves only:

- model execution started
- training progressed to at least step 10
- loss was being computed

It does not prove:

- decoder quality
- eval loss
- leak safety
- non-repetition
- cleanup safety
- product readiness

The next valid state after recovery is not expansion. It is cleanup hardening, probe rerun, and telemetry audit.

