# Stage758 100M Factorized Binding Route

This route wraps the current generalized KBPP algorithm around a 100M model without relaxing the qidless, no-answer-leakage, held-out alias gates.

## Current State

- Best completed 16k answer KBPP: `372.46443714113553`
- Best completed 16k exact KBPP: `365.7994972816619`
- Current factor mode: `text_multi_axis_nonanswer_entity_pair`
- 256 status: `True`
- Blocker: The 256 answer/exact gate is closed on the stable 2048-domain surface. The next 16k gate is 512 KBPP before a real 100M short-probe budget.

## 100M Dry Run

- Status: `passed`
- Parameter count: `101463808`
- Factor mode: `text_multi_axis_nonanswer_entity_pair`
- Artifact: `runs/local/artifacts/stage758_100m_factorized_binding_dry_run/agentkernel_lite_encdec_manifest.json`
- Note: Dry run validates architecture/config compatibility only; it does not train or prove 100M KBPP.

## 100M Targets

- `kbpp_256`: `25600000000` verified bits
- `kbpp_512`: `51200000000` verified bits
- `kbpp_1024`: `102400000000` verified bits

## Algorithm Components

- `qidless held-out alias surfaces`: No qid text, held-out eval entity aliases, and collision selectors remain mandatory.
- `compositional binding ids`: Use semantic axes and non-answer entities only: no answer value, no row id, no full qid.
- `factorized binding head`: Move the factor from post-hoc scoring into a trainable auxiliary head for 100M, with the same ids used at eval.
- `verified-bit training curriculum`: Sample and weight examples by recoverable verified bits, residual collision groups, and held-out family gaps.
- `general path distillation`: The final 100M must answer through its normal text path; the binding head can train and rerank but cannot be the only oracle.

## Training Phases

- `phase0_16k_gate_close`: Scale and profile the accepted multi-axis factor toward the 512 KBPP rung on the 16k microscope. Gate: answer_kbpp >= 512 on qidless held-out alias collision eval, or a stable ceiling is documented.
- `phase1_100m_dry_run`: Verify the 100M architecture, tokenizer, and factorized binding ids compile and produce a manifest without training. Gate: dry-run bundle has correct factor mode and parameter count near 100M.
- `phase2_100m_short_probe`: Run 100M for a short fixed budget on the 128/256 surfaces. Gate: 100M answer KBPP exceeds the 16k density curve after parameter normalization and does not rely on qid/answer leakage.
- `phase3_7b_baseline`: Score a representative 7B on the same verified-bit benchmark. Gate: 100M projected KBPP exceeds measured 7B useful KBPP with margin.
- `phase4_1024_route`: Scale surface entropy and factor recovery until 1024 KBPP is reached or a stable ceiling is mapped. Gate: 1024 answer KBPP = 102.4B verified bits at 100M.

## Command Templates

### 100m_dry_run

```bash
/home/peyton/miniconda3/envs/ai/bin/python legacy_src/scripts/train_agentkernel_lite_encdec.py --dataset-manifest runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json --output-dir runs/local/artifacts/stage758_100m_factorized_binding_dry_run --preset 100m --tokenizer-kind agentkernel-bpe --max-steps 1 --batch-size 8 --eval-every 0 --device cpu --dry-run 1 --decoder-loss-weight 0 --retrieval-factorized-contrastive-weight 1.0 --retrieval-factor-score-weight 4.0 --retrieval-factor-key-hash-mode text_multi_axis_nonanswer_entity_pair --retrieval-factor-key-hash-buckets 32 --retrieval-factor-key-hash-slots 8
```

### 100m_short_probe

```bash
/home/peyton/miniconda3/envs/ai/bin/python legacy_src/scripts/train_agentkernel_lite_encdec.py --dataset-manifest runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json --output-dir runs/local/artifacts/stage758_100m_factorized_binding_short_probe --preset 100m --max-steps 200 --batch-size 8 --eval-every 0 --device cuda --dry-run 0 --decoder-loss-weight 0 --retrieval-factorized-contrastive-weight 1.0 --retrieval-factor-score-weight 4.0 --retrieval-factor-key-hash-mode text_multi_axis_nonanswer_entity_pair --retrieval-factor-key-hash-buckets 32 --retrieval-factor-key-hash-slots 8
```

### strict_eval

```bash
/home/peyton/miniconda3/envs/ai/bin/python scripts/evaluate_retrieval_factor_grid_fast.py --bundle-dir runs/local/artifacts/stage758_100m_factorized_binding_short_probe --dataset-manifest runs/local/tmp/stage751_generalized_256kbpp_collision_surface_d1792/agentkernel_lite_encdec_dataset_manifest.json --device cuda --batch-size 512 --key-factor-modes text_multi_axis_nonanswer_entity_pair --key-factor-weights 4.0 --output-json runs/local/artifacts/stage758_100m_factorized_binding_short_probe_eval.json
```

## Acceptance Rules

- No qid tokens in eval text.
- No answer value included in factor ids.
- Eval entities must remain held-out aliases.
- Collision selectors must remain non-singleton enough that full key lookup cannot explain the score.
- 7B comparison must use the same verified-bit scorer.

## Next Local Action

Build a stable 512-rung surface and evaluate text_multi_axis_nonanswer_entity_pair before running a real 100M short probe.
