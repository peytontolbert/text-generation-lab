from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import torch
from torch import nn
import torch.nn.functional as F


DEFAULT_STRUCTURED_HEAD_DIMS: dict[str, int] = {
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
    "action_sequence": 64,
    "file_plan": 64,
    "symbol_binding": 6,
    "edit_localization": 7,
    "patch_operator": 12,
    "verifier_repair": 9,
    "suffix_choice": 32,
    "episode_repair_outcome": 4,
    "episode_failure_type": 12,
    "episode_boundary_match": 2,
    "episode_target_prefix_match": 2,
    "episode_step_value": 2,
}


@dataclass
class AgentKernelLiteTransformerConfig:
    vocab_size: int = 1506
    d_model: int = 640
    d_ff: int = 2048
    n_layers: int = 6
    n_heads: int = 10
    dropout: float = 0.0
    pad_token_id: int = 0
    max_position_embeddings: int = 4096
    rope_theta: float = 1_000_000.0
    retrieval_head_dim: int | None = 128
    agent_policy_heads: bool = True
    agent_intent_labels: int = 18
    agent_controller_dim: int = 128
    scalar_invariant_rank: int = 32
    structured_head_dims: dict[str, int] = field(default_factory=lambda: dict(DEFAULT_STRUCTURED_HEAD_DIMS))

    @classmethod
    def from_recovered_target_json(cls, payload: dict[str, Any]) -> "AgentKernelLiteTransformerConfig":
        cfg = payload.get("model_config", payload)
        return cls(
            vocab_size=int(cfg.get("vocab_size", 1506)),
            d_model=int(cfg.get("d_model", 640)),
            d_ff=int(cfg.get("d_ff", 2048)),
            n_layers=int(cfg.get("n_layers", 6)),
            n_heads=int(cfg.get("n_heads", 10)),
            dropout=float(cfg.get("resid_dropout", cfg.get("dropout", 0.0)) or 0.0),
            pad_token_id=int(cfg.get("pad_token_id", 0) or 0),
            max_position_embeddings=int(cfg.get("max_position_embeddings", 4096) or 4096),
            rope_theta=float(cfg.get("rope_theta", 1_000_000.0) or 1_000_000.0),
            retrieval_head_dim=(int(cfg.get("retrieval_head_dim")) if cfg.get("retrieval_head_dim") else None),
            agent_policy_heads=bool(cfg.get("agent_policy_heads", True)),
            agent_intent_labels=int(cfg.get("agent_intent_labels", 18) or 0),
            agent_controller_dim=int(cfg.get("agent_controller_dim", 128) or 0),
            scalar_invariant_rank=int(cfg.get("scalar_invariant_rank", 32) or 0),
        )

    @property
    def head_dim(self) -> int:
        if self.d_model % self.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")
        return self.d_model // self.n_heads


class RotaryEmbedding(nn.Module):
    def __init__(self, dim: int, *, base: float = 1_000_000.0, max_position_embeddings: int = 4096) -> None:
        super().__init__()
        self.dim = int(dim)
        self.base = float(base)
        self.max_position_embeddings = int(max_position_embeddings)
        inv_freq = 1.0 / (self.base ** (torch.arange(0, self.dim, 2, dtype=torch.float32) / self.dim))
        self.register_buffer("inv_freq", inv_freq, persistent=False)

    def forward(self, seq_len: int, *, device: torch.device, dtype: torch.dtype) -> tuple[torch.Tensor, torch.Tensor]:
        positions = torch.arange(int(seq_len), device=device, dtype=self.inv_freq.dtype)
        freqs = torch.einsum("i,j->ij", positions, self.inv_freq.to(device=device))
        emb = torch.cat((freqs, freqs), dim=-1)
        return emb.cos().to(dtype=dtype), emb.sin().to(dtype=dtype)


def rotate_half(x: torch.Tensor) -> torch.Tensor:
    x1 = x[..., : x.shape[-1] // 2]
    x2 = x[..., x.shape[-1] // 2 :]
    return torch.cat((-x2, x1), dim=-1)


def apply_rotary(q: torch.Tensor, k: torch.Tensor, cos: torch.Tensor, sin: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
    cos = cos.view(1, 1, cos.shape[0], cos.shape[1])
    sin = sin.view(1, 1, sin.shape[0], sin.shape[1])
    return (q * cos) + (rotate_half(q) * sin), (k * cos) + (rotate_half(k) * sin)


class MultiHeadAttention(nn.Module):
    def __init__(self, config: AgentKernelLiteTransformerConfig, *, causal: bool, use_rope: bool) -> None:
        super().__init__()
        self.config = config
        self.causal = bool(causal)
        self.use_rope = bool(use_rope)
        self.q_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.k_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.v_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.o_proj = nn.Linear(config.d_model, config.d_model, bias=False)
        self.dropout = nn.Dropout(config.dropout) if config.dropout else nn.Identity()
        self.rotary = RotaryEmbedding(
            config.head_dim,
            base=config.rope_theta,
            max_position_embeddings=config.max_position_embeddings,
        )

    def _split(self, x: torch.Tensor) -> torch.Tensor:
        bsz, seq_len, _ = x.shape
        return x.view(bsz, seq_len, self.config.n_heads, self.config.head_dim).transpose(1, 2)

    def _merge(self, x: torch.Tensor) -> torch.Tensor:
        bsz, _, seq_len, _ = x.shape
        return x.transpose(1, 2).contiguous().view(bsz, seq_len, self.config.d_model)

    def forward(
        self,
        query: torch.Tensor,
        key_value: torch.Tensor | None = None,
        key_padding_mask: torch.Tensor | None = None,
    ) -> torch.Tensor:
        source = query if key_value is None else key_value
        q = self._split(self.q_proj(query))
        k = self._split(self.k_proj(source))
        v = self._split(self.v_proj(source))
        if self.use_rope and key_value is None:
            cos, sin = self.rotary(q.shape[-2], device=q.device, dtype=q.dtype)
            q, k = apply_rotary(q, k, cos, sin)
        attn_mask = None
        mask_dtype = q.dtype if q.dtype.is_floating_point else torch.float32
        if self.causal:
            t = q.shape[-2]
            future_block = torch.ones((t, t), dtype=torch.bool, device=q.device).triu(1)
            attn_mask = torch.zeros((t, t), dtype=mask_dtype, device=q.device).masked_fill(future_block, float("-inf"))
        if key_padding_mask is not None:
            padding_block = ~key_padding_mask.to(device=q.device, dtype=torch.bool)
            padding_block = padding_block[:, None, None, :]
            padding_mask = torch.zeros(padding_block.shape, dtype=mask_dtype, device=q.device).masked_fill(padding_block, float("-inf"))
            if attn_mask is None:
                attn_mask = padding_mask
            else:
                attn_mask = attn_mask[None, None, :, :] + padding_mask
        out = F.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=attn_mask,
            dropout_p=float(self.config.dropout if self.training else 0.0),
            is_causal=False,
        )
        return self.o_proj(self._merge(out))


class FeedForward(nn.Module):
    def __init__(self, config: AgentKernelLiteTransformerConfig) -> None:
        super().__init__()
        # Recovered model-stack MLP uses a gated input projection for the 100M path.
        self.up_proj = nn.Linear(config.d_model, 2 * config.d_ff, bias=False)
        self.down_proj = nn.Linear(config.d_ff, config.d_model, bias=False)
        self.dropout = nn.Dropout(config.dropout) if config.dropout else nn.Identity()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        gate, value = self.up_proj(x).chunk(2, dim=-1)
        return self.down_proj(self.dropout(F.silu(gate) * value))


class EncoderLayer(nn.Module):
    def __init__(self, config: AgentKernelLiteTransformerConfig) -> None:
        super().__init__()
        self.self_attn = MultiHeadAttention(config, causal=False, use_rope=True)
        self.mlp = FeedForward(config)
        self.norm1 = nn.LayerNorm(config.d_model)
        self.norm2 = nn.LayerNorm(config.d_model)

    def forward(self, x: torch.Tensor, padding_mask: torch.Tensor | None = None) -> torch.Tensor:
        x = x + self.self_attn(self.norm1(x), key_padding_mask=padding_mask)
        x = x + self.mlp(self.norm2(x))
        return x


class DecoderLayer(nn.Module):
    def __init__(self, config: AgentKernelLiteTransformerConfig) -> None:
        super().__init__()
        self.self_attn = MultiHeadAttention(config, causal=True, use_rope=True)
        self.self_mlp = FeedForward(config)
        self.cross_attn = MultiHeadAttention(config, causal=False, use_rope=False)
        self.cross_mlp = FeedForward(config)
        self.norm1 = nn.LayerNorm(config.d_model)
        self.norm2 = nn.LayerNorm(config.d_model)
        self.norm3 = nn.LayerNorm(config.d_model)
        self.norm4 = nn.LayerNorm(config.d_model)

    def forward(self, x: torch.Tensor, memory: torch.Tensor, memory_mask: torch.Tensor | None = None) -> torch.Tensor:
        x = x + self.self_attn(self.norm1(x))
        x = x + self.self_mlp(self.norm2(x))
        x = x + self.cross_attn(self.norm3(x), key_value=memory, key_padding_mask=memory_mask)
        x = x + self.cross_mlp(self.norm4(x))
        return x


class AgentKernelLiteTransformerSeq2Seq(nn.Module):
    """Recovered transformer/rotary seq2seq interface for the 100M maintainer path.

    This module restores the architecture class we need for shape and parameter-count
    audits. It does not authorize training by itself; trainer authority still comes
    from manifest gates and Stage summaries.
    """

    def __init__(self, config: AgentKernelLiteTransformerConfig | None = None) -> None:
        super().__init__()
        self.config = config or AgentKernelLiteTransformerConfig()
        cfg = self.config
        self.enc_embed = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=cfg.pad_token_id)
        self.dec_embed = nn.Embedding(cfg.vocab_size, cfg.d_model, padding_idx=cfg.pad_token_id)
        self.encoder = nn.ModuleList([EncoderLayer(cfg) for _ in range(cfg.n_layers)])
        self.decoder = nn.ModuleList([DecoderLayer(cfg) for _ in range(cfg.n_layers)])
        self.enc_norm = nn.LayerNorm(cfg.d_model)
        self.dec_norm = nn.LayerNorm(cfg.d_model)
        self.lm_head = nn.Linear(cfg.d_model, cfg.vocab_size, bias=False)
        self.lm_head.weight = self.enc_embed.weight
        if cfg.retrieval_head_dim:
            self.retrieval_query_head = nn.Linear(cfg.d_model, cfg.retrieval_head_dim, bias=False)
            self.retrieval_doc_head = nn.Linear(cfg.d_model, cfg.retrieval_head_dim, bias=False)
        else:
            self.retrieval_query_head = None
            self.retrieval_doc_head = None
        self.agent_policy_heads = nn.ModuleDict(
            {
                "query_confidence": nn.Linear(cfg.d_model, 1),
                "retrieval_coverage": nn.Linear(cfg.d_model, 1),
                "ood_query": nn.Linear(cfg.d_model, 1),
                "ood_evidence": nn.Linear(cfg.d_model, 1),
                "answer_confidence": nn.Linear(cfg.d_model, 1),
                "needs_verification": nn.Linear(cfg.d_model, 1),
                "paper_action_validity": nn.Linear(cfg.d_model, 1),
            }
        ) if cfg.agent_policy_heads else nn.ModuleDict()
        self.agent_intent_head = nn.Linear(cfg.d_model, cfg.agent_intent_labels) if cfg.agent_intent_labels > 0 else None
        self.agent_controller = nn.Linear(cfg.d_model, cfg.agent_controller_dim) if cfg.agent_controller_dim > 0 else None
        self.scalar_invariant = nn.Linear(cfg.d_model, cfg.scalar_invariant_rank, bias=False) if cfg.scalar_invariant_rank > 0 else None
        self.structured_heads = nn.ModuleDict({name: nn.Linear(cfg.d_model, dim) for name, dim in cfg.structured_head_dims.items()})

    def encode(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        x = self.enc_embed(input_ids)
        padding_mask = attention_mask if attention_mask is not None else input_ids.ne(self.config.pad_token_id)
        for layer in self.encoder:
            x = layer(x, padding_mask)
        return self.enc_norm(x)

    def encode_pooled(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        hidden = self.encode(input_ids, attention_mask)
        mask = (attention_mask if attention_mask is not None else input_ids.ne(self.config.pad_token_id)).to(hidden.dtype).unsqueeze(-1)
        return (hidden * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)

    def decode(self, decoder_input_ids: torch.Tensor, memory: torch.Tensor, memory_mask: torch.Tensor | None = None) -> torch.Tensor:
        x = self.dec_embed(decoder_input_ids)
        for layer in self.decoder:
            x = layer(x, memory, memory_mask)
        return self.dec_norm(x)

    def retrieval_query_embedding(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        pooled = self.encode_pooled(input_ids, attention_mask)
        if self.retrieval_query_head is not None:
            pooled = self.retrieval_query_head(pooled)
        return F.normalize(pooled.float(), dim=-1)

    def retrieval_doc_embedding(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> torch.Tensor:
        pooled = self.encode_pooled(input_ids, attention_mask)
        if self.retrieval_doc_head is not None:
            pooled = self.retrieval_doc_head(pooled)
        return F.normalize(pooled.float(), dim=-1)

    def agent_policy_logits(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        pooled = self.encode_pooled(input_ids, attention_mask)
        return {name: head(pooled).squeeze(-1).float() for name, head in self.agent_policy_heads.items()}

    def forward(
        self,
        input_ids: torch.Tensor,
        decoder_input_ids: torch.Tensor,
        attention_mask: torch.Tensor | None = None,
    ) -> dict[str, Any]:
        memory = self.encode(input_ids, attention_mask)
        dec_hidden = self.decode(decoder_input_ids, memory, attention_mask)
        pooled = self._pool_memory(memory, attention_mask, input_ids)
        structured_logits = {name: head(pooled) for name, head in self.structured_heads.items()}
        policy_logits = {name: head(pooled).squeeze(-1).float() for name, head in self.agent_policy_heads.items()}
        if self.agent_intent_head is not None:
            structured_logits["agent_intent"] = self.agent_intent_head(pooled)
        return {
            "decoder_logits": self.lm_head(dec_hidden),
            "structured_logits": structured_logits,
            "agent_policy_logits": policy_logits,
            "pooled": pooled,
        }

    def _pool_memory(self, memory: torch.Tensor, attention_mask: torch.Tensor | None, input_ids: torch.Tensor) -> torch.Tensor:
        mask = (attention_mask if attention_mask is not None else input_ids.ne(self.config.pad_token_id)).to(memory.dtype).unsqueeze(-1)
        return (memory * mask).sum(dim=1) / mask.sum(dim=1).clamp_min(1.0)

    def decoder_ce_loss(self, logits: torch.Tensor, labels: torch.Tensor, row_mask: torch.Tensor | None = None) -> torch.Tensor:
        token_loss = F.cross_entropy(logits.reshape(-1, logits.size(-1)), labels.reshape(-1), ignore_index=0, reduction="none").reshape(labels.shape)
        row_loss = token_loss.sum(dim=1) / labels.ne(0).sum(dim=1).clamp_min(1)
        if row_mask is not None:
            row_loss = row_loss[row_mask]
        if row_loss.numel() == 0:
            return logits.sum() * 0.0
        return row_loss.mean()


def estimate_transformer_parameter_count(config: AgentKernelLiteTransformerConfig) -> int:
    cfg = config
    embed = cfg.vocab_size * cfg.d_model * 2
    tied_lm_head = 0
    # Per encoder layer: q/k/v/o + gated FF up/down + 2 layer norms.
    encoder_layer = (4 * cfg.d_model * cfg.d_model) + (3 * cfg.d_model * cfg.d_ff) + (4 * cfg.d_model)
    # Per decoder layer: self q/k/v/o + self gated FF + cross q/k/v/o + cross gated FF + 4 layer norms.
    decoder_layer = (8 * cfg.d_model * cfg.d_model) + (6 * cfg.d_model * cfg.d_ff) + (8 * cfg.d_model)
    norms = 4 * cfg.d_model
    retrieval = 0 if not cfg.retrieval_head_dim else 2 * cfg.d_model * cfg.retrieval_head_dim
    policy = (7 * (cfg.d_model + 1)) if cfg.agent_policy_heads else 0
    intent = (cfg.d_model + 1) * cfg.agent_intent_labels if cfg.agent_intent_labels > 0 else 0
    controller = (cfg.d_model + 1) * cfg.agent_controller_dim if cfg.agent_controller_dim > 0 else 0
    scalar = cfg.d_model * cfg.scalar_invariant_rank if cfg.scalar_invariant_rank > 0 else 0
    structured = sum((cfg.d_model + 1) * dim for dim in cfg.structured_head_dims.values())
    return int(embed + tied_lm_head + cfg.n_layers * (encoder_layer + decoder_layer) + norms + retrieval + policy + intent + controller + scalar + structured)
