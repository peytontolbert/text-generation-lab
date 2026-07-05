# Stage8814 Transformer Path Study Graph Attachment

Passed: `True`

This indexes the transformer-specific mental model for this lab:

1. Tensor shapes: `[batch, seq] -> [batch, seq, d_model] -> [batch, heads, seq, head_dim] -> [batch, seq, vocab]`.
2. Matmul/projections: `nn.Linear` as learned projections for Q/K/V/O, MLP up/down, LM head, retrieval heads, and structured heads.
3. Attention: QKV projection, head split/merge, RoPE, masks, scaled dot-product attention.
4. State: encoder memory plus decoder causal/cross-attention hidden state, not generic SSM theory first.
5. Learning: decoder CE/logits/autograd/backward/clip/optimizer step in the recovered training loop.

Primary files:

- `legacy_src/agentkernel_lite/modeling_transformer.py`
- `legacy_src/agentkernel_lite/training_loop.py`
- `tests/test_transformer_recovery.py`
- `docs/LOW_LEVEL_TRAINING_CONCEPT_SESSION_GREP_STAGE8703.md`

The GRU scaffold is fallback, not the main intelligence path for this repo.

No training, runtime, decoder CE, denoise CE, source/body emission, scoring, Gemma, controller merge, or promotion is authorized by this stage.
