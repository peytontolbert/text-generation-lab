# Stage9396 Training Loop Frontier Diagnosis Contract

Stage9395 fixed the mechanics that were still ambiguous after Stage9393:

- target resolver surfaces are repaired by Stage9391
- generation cap is no longer clipping short byte/BPE targets
- train rows overfit exactly
- eval/strict rows still fail
- leaks, repetition, short/junk, and unterminated output are zero

## Active Training Mechanics

- Tokenization: `agentkernel_bytelevel_bpe_v1`, vocab 1506, hashlock required.
- Loss masking: current probes enable `denoise_ce` only; `decoder_ce` remains closed.
- Post-prefix masking: denoise probes train only suffix tokens after `model_input.active_generation_prefix_span`.
- Optimizer: AdamW with tiny-probe LR.
- Gradients: `clip_grad_norm_(..., 1.0)` plus pre/post clip telemetry.
- Evaluation: `eval` and `strict_eval` run under `no_grad` and emit split loss records.
- Telemetry: `row_token_loss`, `row_gradient_norms`, `row_dynamics_history`, `activation_summary`, `module_delta_norms`, generation audits.
- Checkpoint safety: no final checkpoint export, no final model save, cleanup proof emitted.

## Not Yet Scale Features

- Gradient accumulation is not required for tiny 23-row probes.
- BF16/mixed precision should wait for determinism and NaN guards.
- AdamW no-decay parameter groups should be added before longer runs.
- Distributed/sharded training is out of scope until scaled manifests exist.
- Checkpoint resume remains closed under the safety-probe contract.

## Current Diagnosis

Stage9395 shows the model can memorize the short-suffix train rows, but it does not generalize to eval/strict suffix families. The next data patch is heldout contrastive suffix support, not broader decoder CE.

## Next Gate

Before any rejoin or wider decoder work, the next probe must hit exact/prefix/boundary/contentful 23/23 with zero short/junk, repetition, leak, and unterminated rows.
