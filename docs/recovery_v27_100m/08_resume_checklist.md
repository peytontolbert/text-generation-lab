# v2.7 Resume Checklist

Use this checklist after restoring the repository.

## 1. Restore Workspace

Required:

```text
/data/agentkernel-seq2seq-text-lab
```

Should contain:

```text
.git or source equivalent
legacy_src/scripts/train_agentkernel_lite_encdec.py
scripts/
runs/
docs/
```

Preserve:

```text
V27_100M_RESEARCH_RECOVERY_NOTES.md
docs/recovery_v27_100m/
```

## 2. Patch Cleanup First

Before any training:

- remove unsafe cleanup logic
- add safe checkpoint cleanup helper
- compile trainer
- test cleanup helper on harmless temp path
- verify it refuses:
  - empty path
  - `.`
  - repo root
  - output root
  - `/`
  - path outside output dir

## 3. Rebuild Stage Context

Recover or recreate:

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

If exact artifacts are gone, recreate them from these docs and prior chat output.

## 4. Verify Bounded Decoder Inputs

Required loss mask:

```text
runs/local/artifacts/stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design/stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design_loss_mask_design.jsonl
```

Expected:

```text
64 rows
train/eval/strict: 32 / 16 / 16
languages: 16 each
surfaces: 16 each
future losses allowed: ["decoder_ce"]
current authority rows: 0
over cap rows: 0
```

Required target source:

```text
runs/local/artifacts/stage8562_v27_bounded_decoder_ce_quarantine_materialization_manifest/stage8562_v27_bounded_decoder_ce_quarantine_materialization_manifest_manifest.jsonl
```

## 5. Verify Runtime

Use:

```text
/home/peyton/miniconda3/envs/code_assist_runtime/bin/python
```

Check:

```bash
/home/peyton/miniconda3/envs/code_assist_runtime/bin/python -c "import torch, torch.nn; print(torch.__version__)"
```

Known good version before deletion:

```text
2.10.0+cu128
```

Do not use bare `python`.

## 6. Rebuild Command

Command must include:

```text
--repo-root /data/agentkernel-seq2seq-text-lab
--mode bounded_decoder_ce_probe
--manifest runs/local/artifacts/stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design/stage8568_v27_bounded_decoder_ce_loss_mask_reopen_design_loss_mask_design.jsonl
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

Do not use cleanup flag until cleanup is safe.

## 7. Required Probe Audit

After a successful tiny probe, audit:

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

Do not expand until telemetry is clean.

## 8. Decision Rules

If probe fails:

```text
diagnose token-level failure
patch target rendering / EOS / loss weighting / row mix
rerun tiny only after audit
```

If probe passes:

```text
expand bounded rows carefully
add graph topology counterbalance
add denoise/repair objective
run next capped probe
```

Never jump straight to full decoder, Gemma comparison, runtime, source/body, harness scoring, or promotion.

