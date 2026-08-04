"""Behavioral tests for the RecurrentGemma maintainer adapter."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
import torch
from torch import nn
import torch.nn.functional as F

from legacy_src.agentkernel_lite.modeling_recurrent_gemma import (
    RecurrentGemmaMaintainerConfig,
    RecurrentGemmaMaintainerModel,
    pool_last_valid_token,
)


class FakeRecurrentGemma(nn.Module):
    """Small causal-LM double that exposes the Transformers output contract."""

    def __init__(self, *, vocab_size: int = 19, hidden_size: int = 8) -> None:
        super().__init__()
        self.config = SimpleNamespace(
            model_type="recurrent_gemma",
            vocab_size=vocab_size,
            hidden_size=hidden_size,
        )
        self.embedding = nn.Embedding(vocab_size, hidden_size)
        self.lm_head = nn.Linear(hidden_size, vocab_size, bias=False)

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
        labels: torch.Tensor | None = None,
        **_: object,
    ) -> SimpleNamespace:
        """Return hidden states, raw logits, loss, and a visible cache marker."""

        hidden = self.embedding(input_ids)
        logits = self.lm_head(hidden)
        loss = None
        if labels is not None:
            loss = F.cross_entropy(
                logits[:, :-1].reshape(-1, logits.size(-1)),
                labels[:, 1:].reshape(-1),
            )
        return SimpleNamespace(
            logits=logits,
            hidden_states=(hidden,),
            loss=loss,
            past_key_values="fake-cache",
        )


def small_config(*, freeze_backbone: bool = True) -> RecurrentGemmaMaintainerConfig:
    """Create a focused task-head config for unit tests."""

    return RecurrentGemmaMaintainerConfig(
        structured_head_dims={"action_label": 5, "decode_allowed": 2},
        freeze_backbone=freeze_backbone,
    )


def test_forward_returns_full_vocab_and_structured_logits() -> None:
    """The adapter preserves raw LM logits while adding policy predictions."""

    model = RecurrentGemmaMaintainerModel(FakeRecurrentGemma(), small_config())
    input_ids = torch.tensor([[2, 3, 4], [5, 6, 0]])
    attention_mask = torch.tensor([[1, 1, 1], [1, 1, 0]])
    output = model(input_ids, attention_mask, labels=input_ids)

    assert output["decoder_logits"].shape == (2, 3, 19)
    assert output["structured_logits"]["action_label"].shape == (2, 5)
    assert output["structured_logits"]["decode_allowed"].shape == (2, 2)
    assert output["pooled"].shape == (2, 8)
    assert output["past_key_values"] == "fake-cache"
    assert output["decoder_loss"].ndim == 0


def test_pooling_handles_left_and_right_padding() -> None:
    """Final-token pooling must support variable-length prompt batches."""

    hidden = torch.arange(2 * 4 * 3, dtype=torch.float32).view(2, 4, 3)
    mask = torch.tensor([[0, 1, 1, 1], [1, 1, 0, 0]])
    pooled = pool_last_valid_token(hidden, mask)

    assert torch.equal(pooled[0], hidden[0, 3])
    assert torch.equal(pooled[1], hidden[1, 1])


def test_pooling_rejects_all_padding_rows() -> None:
    """An all-padding row cannot produce a meaningful maintainer state."""

    with pytest.raises(ValueError, match="at least one valid token"):
        pool_last_valid_token(torch.zeros(1, 3, 4), torch.zeros(1, 3))


def test_frozen_backbone_stays_in_eval_and_only_heads_receive_gradients() -> None:
    """Head-only tuning should be deterministic and memory-efficient."""

    backbone = FakeRecurrentGemma()
    model = RecurrentGemmaMaintainerModel(backbone, small_config())
    model.train()
    output = model(
        torch.tensor([[2, 3, 4]]),
        torch.ones(1, 3, dtype=torch.long),
    )
    loss = model.structured_loss(
        output["structured_logits"],
        {"action_label": torch.tensor([3])},
    )
    loss.backward()

    assert model.training is True
    assert backbone.training is False
    assert all(parameter.grad is None for parameter in backbone.parameters())
    assert any(
        parameter.grad is not None for parameter in model.structured_heads.parameters()
    )


def test_unfrozen_backbone_receives_structured_head_gradients() -> None:
    """Full or adapter tuning can propagate policy loss into the backbone."""

    backbone = FakeRecurrentGemma()
    model = RecurrentGemmaMaintainerModel(
        backbone,
        small_config(freeze_backbone=False),
    )
    output = model(torch.tensor([[2, 3, 4]]), torch.ones(1, 3, dtype=torch.long))
    loss = output["structured_logits"]["decode_allowed"].sum()
    loss.backward()

    assert any(parameter.grad is not None for parameter in backbone.parameters())


def test_parameter_summary_separates_backbone_and_new_heads() -> None:
    """Run cards can distinguish inherited weights from trained task heads."""

    model = RecurrentGemmaMaintainerModel(FakeRecurrentGemma(), small_config())
    summary = model.parameter_summary()

    assert summary["total"] == summary["backbone"] + summary["structured_heads"]
    assert summary["trainable"] == summary["structured_heads"]


def test_rejects_non_recurrent_backbone_by_default() -> None:
    """Checkpoint identity mistakes fail before training or inference."""

    backbone = FakeRecurrentGemma()
    backbone.config.model_type = "gemma"
    with pytest.raises(ValueError, match="expected a RecurrentGemma backbone"):
        RecurrentGemmaMaintainerModel(backbone, small_config())


def test_installed_transformers_recurrent_gemma_contract() -> None:
    """Exercise the adapter against a tiny native Transformers backbone."""

    transformers = pytest.importorskip("transformers")
    backbone_config = transformers.RecurrentGemmaConfig(
        num_hidden_layers=3,
        vocab_size=32,
        hidden_size=16,
        intermediate_size=48,
        num_attention_heads=2,
        num_key_value_heads=1,
        lru_width=16,
        attention_window_size=4,
        block_types=("recurrent", "recurrent", "attention"),
    )
    backbone = transformers.RecurrentGemmaForCausalLM(backbone_config)
    model = RecurrentGemmaMaintainerModel(
        backbone,
        RecurrentGemmaMaintainerConfig(
            structured_head_dims={"action": 3},
            freeze_backbone=True,
        ),
    )
    output = model(
        torch.tensor([[2, 4, 5, 1]]),
        torch.ones(1, 4, dtype=torch.long),
    )

    assert output["decoder_logits"].shape == (1, 4, 32)
