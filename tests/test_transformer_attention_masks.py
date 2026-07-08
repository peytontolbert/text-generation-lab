from __future__ import annotations

import torch

from legacy_src.agentkernel_lite import modeling_transformer as mt


def test_causal_attention_uses_additive_negative_infinity_mask(monkeypatch):
    cfg = mt.AgentKernelLiteTransformerConfig(d_model=20, n_heads=2, d_ff=32, n_layers=1, vocab_size=64)
    attn = mt.MultiHeadAttention(cfg, causal=True, use_rope=False)
    captured = {}

    def fake_sdpa(q, k, v, *, attn_mask=None, dropout_p=0.0, is_causal=False):
        captured["attn_mask"] = attn_mask.detach().clone()
        captured["is_causal"] = is_causal
        return torch.zeros_like(q)

    monkeypatch.setattr(mt.F, "scaled_dot_product_attention", fake_sdpa)
    query = torch.randn(1, 4, cfg.d_model)
    attn(query)
    mask = captured["attn_mask"]
    assert captured["is_causal"] is False
    assert mask.dtype.is_floating_point
    assert mask.shape == (4, 4)
    assert torch.isneginf(mask[0, 1])
    assert torch.isneginf(mask[0, 3])
    assert mask[0, 0].item() == 0.0
    assert mask[3, 0].item() == 0.0


def test_padding_attention_uses_additive_negative_infinity_mask(monkeypatch):
    cfg = mt.AgentKernelLiteTransformerConfig(d_model=20, n_heads=2, d_ff=32, n_layers=1, vocab_size=64)
    attn = mt.MultiHeadAttention(cfg, causal=False, use_rope=False)
    captured = {}

    def fake_sdpa(q, k, v, *, attn_mask=None, dropout_p=0.0, is_causal=False):
        captured["attn_mask"] = attn_mask.detach().clone()
        return torch.zeros_like(q)

    monkeypatch.setattr(mt.F, "scaled_dot_product_attention", fake_sdpa)
    query = torch.randn(1, 3, cfg.d_model)
    attn(query, key_padding_mask=torch.tensor([[True, True, False]]))
    mask = captured["attn_mask"]
    assert mask.dtype.is_floating_point
    assert mask.shape == (1, 1, 1, 3)
    assert mask[0, 0, 0, 0].item() == 0.0
    assert mask[0, 0, 0, 1].item() == 0.0
    assert torch.isneginf(mask[0, 0, 0, 2])
