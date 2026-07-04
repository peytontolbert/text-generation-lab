# Trainer Rebuild Contract

This document records the recovered trainer surface after the workspace-loss incident.

## Current State

`legacy_src/scripts/train_agentkernel_lite_encdec.py` has been rebuilt as a closed-boundary scaffold. It is not a full trainer yet.

It supports the Stage8580/8586 command surface required for the bounded decoder CE probe:

- `--repo-root`
- `--manifest`
- `--mode bounded_decoder_ce_probe`
- `--max-train-rows`
- `--max-eval-rows`
- `--max-strict-rows`
- `--max-steps`
- `--max-decoder-tokens`
- `--decoder-ce-weight`
- `--structured-aux-weight`
- `--denoise-weight`
- `--require-loss-mask-enforcement-audit`
- `--no-final-checkpoint-export`
- `--cleanup-checkpoints-after-probe`
- `--skip-final-model-save 1`
- `--output-dir`
- `--run-id`
- `--contract-only`

## What It Does

In `bounded_decoder_ce_probe` contract mode it verifies:

- output directory is under the declared repo root
- manifest exists and is JSONL
- train/eval/strict caps are not exceeded
- every row enables only `decoder_ce`
- denoise/runtime/structured losses are not active for this probe
- row authority flags are closed
- target token lengths do not exceed `--max-decoder-tokens` when present
- `--require-loss-mask-enforcement-audit` is present
- `--no-final-checkpoint-export` is present
- `--skip-final-model-save 1` is present
- cleanup is only represented by a safe dry-run proof

It emits non-executing audit artifacts under the output directory, including:

- `probe_contract_audit.json`
- placeholder telemetry files required by the Stage8580 probe contract
- `cleanup_proof.json`
- `cleanup_dry_run.json` when cleanup is requested

## What It Does Not Do

The scaffold does not train a model, export a checkpoint, run runtime tools, run Gemma, run harness scoring, emit source/body output, or authorize decoder CE training.

If invoked without `--contract-only`, it validates the contract and then exits non-zero with a message that model execution is disabled.

## Why This Exists

Stage8580 failed because the active trainer command surface did not match the audited bounded decoder CE probe contract. This rebuild restores the command/runtime validation surface without reopening execution.

Next steps:

1. Rebuild bounded decoder CE wrapper/audit scripts against this command surface.
2. Re-run final pre-execution audit in non-executing mode.
3. Only after a separate explicit authorization stage should real tiny execution implementation be considered.
