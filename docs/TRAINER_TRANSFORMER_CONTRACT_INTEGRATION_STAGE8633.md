# Stage8633 Trainer Transformer Contract Integration

This stage reconnects the recovered transformer/rotary implementation to the safe trainer command surface without authorizing model execution or training.

## What Changed

- `legacy_src/scripts/train_agentkernel_lite_encdec.py` now accepts `--implementation scaffold|transformer`.
- Contract-only mode records `implementation: transformer` without instantiating the model.
- The transformer module remains `legacy_src/agentkernel_lite/modeling_transformer.py`.
- Existing trainer safety gates, row caps, loss-mask checks, no-final-checkpoint-export, and cleanup contracts remain active.

## Why It Matters

Stage8631 recovered the 102M-compatible transformer module. Stage8633 ensures the trainer control plane can refer to it explicitly, so future bounded probes do not accidentally use the GRU scaffold when the audit expects the recovered transformer.

## Still Closed

Model execution, decoder CE training, runtime, source/body emission, Gemma, harness/scoring, controller merge, and promotion remain closed.

## Metrics

```json
{
  "authority_opened": 0,
  "model_execution_attempted": false,
  "tests_passed": 34,
  "tests_skipped": 2,
  "trainer_implementation_flag_present": true,
  "transformer_contract_records_without_execution": true
}
```
