# Stage8631 Recovered Transformer Module Audit

This stage records the local recovery of the transformer/rotary implementation needed for the 100M software-maintainer path. It does not authorize training or model execution.

## What Was Recovered

- local module: `legacy_src/agentkernel_lite/modeling_transformer.py`
- transformer encoder/decoder stack with RoPE decoder self-attention
- cross-attention decoder layers
- structured-state heads for the recovered curriculum objectives
- retrieval query/doc embedding heads
- agent policy and intent heads
- decoder CE loss helper with row mask support
- target-config parameter-count estimator

## Why This Matters

Stage8629 proved the active model was only a GRU scaffold. Stage8630 found the preserved architecture boundary in `/data/transformer_10/runtime/seq2seq.py` plus transformer/rotary runtime modules. Stage8631 restores a local, auditable transformer module so the next step can be a non-executing shape and parameter-count audit.

## Metrics

```json
{
  "estimate_to_preserved_ratio": 0.999469891011548,
  "estimated_local_transformer_parameter_count": 102599944,
  "missing_marker_count": 0,
  "required_marker_count": 15,
  "required_marker_hits": 15,
  "target_d_model": 640,
  "target_heads": 10,
  "target_layers": 6,
  "target_parameter_count": 102654362,
  "target_vocab_size": 1506
}
```

## Still Closed

Decoder CE, runtime, source/body emission, Gemma, harness/scoring, controller merge, and promotion remain closed.
