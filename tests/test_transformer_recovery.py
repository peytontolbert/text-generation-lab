from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip("torch")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "legacy_src"))

from agentkernel_lite import (  # noqa: E402
    AgentKernelLiteTransformerConfig,
    AgentKernelLiteTransformerSeq2Seq,
    estimate_transformer_parameter_count,
)


def tiny_config() -> AgentKernelLiteTransformerConfig:
    return AgentKernelLiteTransformerConfig(
        vocab_size=64,
        d_model=32,
        d_ff=64,
        n_layers=1,
        n_heads=4,
        retrieval_head_dim=16,
        agent_intent_labels=5,
        agent_controller_dim=8,
        scalar_invariant_rank=4,
        structured_head_dims={
            "build_mode": 3,
            "action_label": 4,
            "decoder_budget_ok": 2,
            "decode_allowed": 2,
        },
    )


def test_recovered_transformer_forward_shapes() -> None:
    cfg = tiny_config()
    model = AgentKernelLiteTransformerSeq2Seq(cfg)
    input_ids = torch.tensor([[1, 7, 8, 2, 0], [1, 9, 2, 0, 0]], dtype=torch.long)
    attention_mask = input_ids.ne(0).long()
    decoder_input_ids = torch.tensor([[1, 10, 11, 2], [1, 12, 2, 0]], dtype=torch.long)
    labels = torch.tensor([[10, 11, 2, 0], [12, 2, 0, 0]], dtype=torch.long)

    out = model(input_ids, decoder_input_ids, attention_mask)
    assert out["decoder_logits"].shape == (2, 4, cfg.vocab_size)
    assert out["structured_logits"]["build_mode"].shape == (2, 3)
    assert out["structured_logits"]["agent_intent"].shape == (2, 5)
    assert set(out["agent_policy_logits"]) >= {"query_confidence", "retrieval_coverage", "needs_verification"}

    row_mask = torch.tensor([True, False])
    loss = model.decoder_ce_loss(out["decoder_logits"], labels, row_mask)
    assert torch.isfinite(loss)


def test_recovered_transformer_retrieval_embeddings_are_normalized() -> None:
    cfg = tiny_config()
    model = AgentKernelLiteTransformerSeq2Seq(cfg)
    input_ids = torch.tensor([[1, 7, 8, 2, 0]], dtype=torch.long)
    attention_mask = input_ids.ne(0).long()
    query = model.retrieval_query_embedding(input_ids, attention_mask)
    doc = model.retrieval_doc_embedding(input_ids, attention_mask)
    assert query.shape == (1, cfg.retrieval_head_dim)
    assert doc.shape == (1, cfg.retrieval_head_dim)
    assert torch.allclose(query.norm(dim=-1), torch.ones(1), atol=1e-5)
    assert torch.allclose(doc.norm(dim=-1), torch.ones(1), atol=1e-5)


def test_recovered_target_config_maps_to_transformer_without_execution() -> None:
    payload = json.loads((ROOT / "configs" / "model" / "agentkernel_100m_seq2seq_recovered_target.json").read_text())
    cfg = AgentKernelLiteTransformerConfig.from_recovered_target_json(payload)
    assert cfg.d_model == 640
    assert cfg.d_ff == 2048
    assert cfg.n_layers == 6
    assert cfg.n_heads == 10
    assert cfg.vocab_size == 1506
    assert cfg.rope_theta == 1_000_000.0
    assert cfg.agent_policy_heads is True
    assert cfg.retrieval_head_dim == 128
    estimated = estimate_transformer_parameter_count(cfg)
    assert estimated > 80_000_000
    assert estimated < 140_000_000
