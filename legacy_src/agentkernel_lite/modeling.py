from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import torch
from torch import nn
import torch.nn.functional as F


@dataclass
class AgentKernelLiteConfig:
    vocab_size: int = 259
    hidden_size: int = 192
    num_layers: int = 2
    dropout: float = 0.0
    structured_head_dims: dict[str, int] = field(default_factory=lambda: {
        "surface_role": 8,
        "repair_surface": 8,
        "action_label": 12,
        "evidence_state": 6,
        "decoder_budget_ok": 2,
        "decode_allowed": 2,
        "build_mode": 5,
        "allowed_import_policy": 4,
        "blocked_import_policy": 4,
        "repo_dependency_policy": 5,
        "file_plan": 64,
    })

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> "AgentKernelLiteConfig":
        scale = str(payload.get("target_scale") or payload.get("parameter_target") or "100m")
        # Recovered config is intentionally conservative. The true 100M width/depth
        # should be restored later from original configs/checkpoints.
        hidden = int(payload.get("hidden_size", 192 if scale == "100m" else 128))
        return cls(hidden_size=hidden)


class AgentKernelLiteSeq2Seq(nn.Module):
    """Small recovered seq2seq implementation scaffold.

    This is importable and trainable for tiny probes, but it is not claimed to be
    the lost production 100M architecture. It restores the expected interfaces:
    encoder packet -> decoder logits + structured heads + masked loss helpers.
    """

    def __init__(self, config: AgentKernelLiteConfig | None = None) -> None:
        super().__init__()
        self.config = config or AgentKernelLiteConfig()
        h = self.config.hidden_size
        self.embedding = nn.Embedding(self.config.vocab_size, h, padding_idx=0)
        self.encoder = nn.GRU(h, h, num_layers=self.config.num_layers, batch_first=True, dropout=self.config.dropout if self.config.num_layers > 1 else 0.0)
        self.decoder = nn.GRU(h, h, num_layers=self.config.num_layers, batch_first=True, dropout=self.config.dropout if self.config.num_layers > 1 else 0.0)
        self.decoder_out = nn.Linear(h, self.config.vocab_size)
        self.structured_heads = nn.ModuleDict({name: nn.Linear(h, dim) for name, dim in self.config.structured_head_dims.items()})

    def forward(self, input_ids: torch.Tensor, decoder_input_ids: torch.Tensor) -> dict[str, Any]:
        enc_emb = self.embedding(input_ids)
        enc_out, hidden = self.encoder(enc_emb)
        pooled = enc_out[:, 0, :]
        dec_emb = self.embedding(decoder_input_ids)
        dec_out, _ = self.decoder(dec_emb, hidden)
        return {
            "decoder_logits": self.decoder_out(dec_out),
            "structured_logits": {name: head(pooled) for name, head in self.structured_heads.items()},
            "pooled": pooled,
        }

    def decoder_ce_loss(self, logits: torch.Tensor, labels: torch.Tensor, row_mask: torch.Tensor | None = None) -> torch.Tensor:
        token_loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), labels.reshape(-1), ignore_index=0, reduction="none").reshape(labels.shape)
        row_loss = token_loss.sum(dim=1) / labels.ne(0).sum(dim=1).clamp_min(1)
        if row_mask is not None:
            row_loss = row_loss[row_mask]
        if row_loss.numel() == 0:
            return logits.sum() * 0.0
        return row_loss.mean()


def module_delta_norms(before: dict[str, torch.Tensor], after: dict[str, torch.Tensor]) -> dict[str, float]:
    groups = {"embedding": 0.0, "encoder": 0.0, "decoder": 0.0, "structured_heads": 0.0, "other": 0.0}
    for name, prev in before.items():
        if name not in after:
            continue
        delta = (after[name] - prev).float().norm().item()
        if name.startswith("embedding"):
            groups["embedding"] += delta
        elif name.startswith("encoder"):
            groups["encoder"] += delta
        elif name.startswith("decoder") or name.startswith("decoder_out"):
            groups["decoder"] += delta
        elif name.startswith("structured_heads"):
            groups["structured_heads"] += delta
        else:
            groups["other"] += delta
    return groups
