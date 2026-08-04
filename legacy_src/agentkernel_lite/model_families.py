"""Reference implementations for the recovered maintainer model families.

These modules make the registry entries executable without granting training or
runtime authority. They are intentionally small, dependency-light PyTorch
building blocks that can be wired into probes once dataset rows and admission
gates exist for the corresponding family.
"""

from __future__ import annotations

import ast
import math
from collections import Counter
from dataclasses import dataclass
from typing import Callable, Iterable, Mapping, Sequence

import torch
from torch import nn
import torch.nn.functional as F

from .modeling_recurrent_gemma import RecurrentGemmaMaintainerModel
from .modeling_transformer import AgentKernelLiteTransformerSeq2Seq


class NGramMarkovPrior:
    """Smoothed token n-gram transition prior for non-authority style signals."""

    def __init__(self, n: int = 3, alpha: float = 0.1) -> None:
        if n < 1:
            raise ValueError("n must be positive")
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        self.n = int(n)
        self.alpha = float(alpha)
        self.context_counts: Counter[tuple[str, ...]] = Counter()
        self.transition_counts: Counter[tuple[tuple[str, ...], str]] = Counter()
        self.vocab: set[str] = set()

    def fit(self, token_sequences: Iterable[Sequence[str]]) -> "NGramMarkovPrior":
        for sequence in token_sequences:
            tokens = ["<bos>"] * (self.n - 1) + [str(token) for token in sequence] + ["<eos>"]
            self.vocab.update(tokens)
            for index in range(self.n - 1, len(tokens)):
                context = tuple(tokens[index - self.n + 1:index]) if self.n > 1 else ()
                token = tokens[index]
                self.context_counts[context] += 1
                self.transition_counts[(context, token)] += 1
        return self

    def transition_log_prob(self, context: Sequence[str], token: str) -> float:
        trimmed = tuple(str(item) for item in context[-max(0, self.n - 1):])
        if self.n > 1 and len(trimmed) < self.n - 1:
            trimmed = ("<bos>",) * (self.n - 1 - len(trimmed)) + trimmed
        vocab_size = max(1, len(self.vocab))
        numerator = self.transition_counts[(trimmed, str(token))] + self.alpha
        denominator = self.context_counts[trimmed] + self.alpha * vocab_size
        return math.log(numerator / denominator)

    def style_anomaly_score(self, tokens: Sequence[str]) -> float:
        if not tokens:
            return 0.0
        padded = ["<bos>"] * (self.n - 1) + [str(token) for token in tokens]
        total = 0.0
        count = 0
        for index in range(self.n - 1, len(padded)):
            context = padded[index - self.n + 1:index] if self.n > 1 else []
            total -= self.transition_log_prob(context, padded[index])
            count += 1
        return total / max(1, count)


class LinearTreeMLPHeads(nn.Module):
    """Transparent route/risk/confidence/OOD heads over structured features."""

    def __init__(self, input_dim: int, hidden_dim: int, route_count: int) -> None:
        super().__init__()
        if min(input_dim, hidden_dim, route_count) <= 0:
            raise ValueError("input_dim, hidden_dim, and route_count must be positive")
        self.trunk = nn.Sequential(
            nn.LayerNorm(input_dim),
            nn.Linear(input_dim, hidden_dim),
            nn.GELU(),
        )
        self.route_head = nn.Linear(hidden_dim, route_count)
        self.risk_head = nn.Linear(hidden_dim, 1)
        self.confidence_head = nn.Linear(hidden_dim, 1)
        self.ood_head = nn.Linear(hidden_dim, 1)
        self.abstain_head = nn.Linear(hidden_dim, 2)

    def forward(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        hidden = self.trunk(features.float())
        return {
            "route_logits": self.route_head(hidden),
            "risk_score": torch.sigmoid(self.risk_head(hidden)).squeeze(-1),
            "confidence": torch.sigmoid(self.confidence_head(hidden)).squeeze(-1),
            "ood_score": torch.sigmoid(self.ood_head(hidden)).squeeze(-1),
            "abstain_or_continue_logits": self.abstain_head(hidden),
        }


class RNNTraceCompressor(nn.Module):
    """GRU/LSTM sidecar for tool/log/action trace state tracking."""

    def __init__(self, input_dim: int, hidden_dim: int, workflow_states: int, *, cell: str = "gru") -> None:
        super().__init__()
        if min(input_dim, hidden_dim, workflow_states) <= 0:
            raise ValueError("input_dim, hidden_dim, and workflow_states must be positive")
        cell = cell.lower()
        if cell == "gru":
            self.rnn: nn.Module = nn.GRU(input_dim, hidden_dim, batch_first=True)
        elif cell == "lstm":
            self.rnn = nn.LSTM(input_dim, hidden_dim, batch_first=True)
        else:
            raise ValueError("cell must be 'gru' or 'lstm'")
        self.workflow_head = nn.Linear(hidden_dim, workflow_states)
        self.loop_head = nn.Linear(hidden_dim, 1)
        self.next_state_head = nn.Linear(hidden_dim, hidden_dim)

    def forward(self, trace_features: torch.Tensor) -> dict[str, torch.Tensor]:
        outputs, hidden = self.rnn(trace_features.float())
        final = hidden[0][-1] if isinstance(hidden, tuple) else hidden[-1]
        return {
            "workflow_state_logits": self.workflow_head(final),
            "loop_risk": torch.sigmoid(self.loop_head(final)).squeeze(-1),
            "next_trace_state": self.next_state_head(final),
            "sequence_states": outputs,
        }


class MambaRepoStateCompressor(nn.Module):
    """CUDA-only Mamba selective-scan compressor for repo/log streams.

    This wrapper intentionally has no diagonal-SSM fallback. If the upstream
    ``mamba_ssm`` package or CUDA execution is unavailable, construction or
    forward fails loudly instead of silently substituting another model family.
    """

    state_vector_kind = "mamba_selective_scan_embedding"

    def __init__(
        self,
        input_dim: int,
        state_dim: int,
        *,
        d_state: int = 16,
        d_conv: int = 4,
        expand: int = 2,
        use_fast_path: bool = True,
        device: torch.device | str | None = None,
        dtype: torch.dtype | None = None,
    ) -> None:
        super().__init__()
        if min(input_dim, state_dim, d_state, d_conv, expand) <= 0:
            raise ValueError("input_dim, state_dim, d_state, d_conv, and expand must be positive")
        try:
            from mamba_ssm.modules.mamba_simple import Mamba
        except Exception as exc:  # pragma: no cover - depends on optional CUDA extension install
            raise ImportError("MambaRepoStateCompressor requires mamba_ssm with CUDA selective-scan support") from exc
        if not torch.cuda.is_available():
            raise RuntimeError("MambaRepoStateCompressor requires CUDA; no CPU fallback is provided")
        if device is None:
            device = torch.device("cuda", torch.cuda.current_device())
        device_obj = torch.device(device)
        if device_obj.type != "cuda":
            raise RuntimeError("MambaRepoStateCompressor must be constructed on CUDA; no CPU fallback is provided")
        self.input_dim = int(input_dim)
        self.state_dim = int(state_dim)
        self.input_proj = nn.Linear(input_dim, state_dim, device=device_obj, dtype=dtype)
        self.mamba = Mamba(
            d_model=state_dim,
            d_state=d_state,
            d_conv=d_conv,
            expand=expand,
            use_fast_path=use_fast_path,
            device=device_obj,
            dtype=dtype,
        )
        self.summary_head = nn.Linear(state_dim, state_dim, device=device_obj, dtype=dtype)
        self.retrieval_hint_head = nn.Linear(state_dim, state_dim, device=device_obj, dtype=dtype)

    def forward(self, repo_stream: torch.Tensor, mask: torch.Tensor | None = None) -> dict[str, torch.Tensor | str | bool]:
        if repo_stream.dim() != 3:
            raise ValueError("repo_stream must have shape [batch, steps, input_dim]")
        if repo_stream.shape[-1] != self.input_dim:
            raise ValueError(f"repo_stream input dim mismatch: expected {self.input_dim}, got {repo_stream.shape[-1]}")
        if not repo_stream.is_cuda:
            raise RuntimeError("MambaRepoStateCompressor requires CUDA input tensors; no CPU fallback is provided")
        stream = self.input_proj(repo_stream)
        if mask is not None:
            stream = stream * mask.to(device=stream.device, dtype=stream.dtype).unsqueeze(-1)
        sequence_states = self.mamba(stream)
        if mask is None:
            final = sequence_states[:, -1]
        else:
            lengths = mask.to(device=stream.device, dtype=torch.long).sum(dim=1).clamp_min(1) - 1
            final = sequence_states.gather(1, lengths.view(-1, 1, 1).expand(-1, 1, sequence_states.shape[-1])).squeeze(1)
        return {
            "compressed_repo_state": final,
            "long_context_summary": self.summary_head(final),
            "retrieval_hints": self.retrieval_hint_head(final),
            "sequence_states": sequence_states,
            "state_vector_kind": self.state_vector_kind,
            "uses_true_mamba_selective_scan": True,
            "fallback_used": False,
        }


class DiagonalStateSpaceRepoCompressor(nn.Module):
    """Non-registry diagonal SSM reference for experiments outside Mamba paths."""

    state_vector_kind = "diagonal_ssm_embedding"

    def __init__(self, input_dim: int, state_dim: int) -> None:
        super().__init__()
        if min(input_dim, state_dim) <= 0:
            raise ValueError("input_dim and state_dim must be positive")
        self.input_proj = nn.Linear(input_dim, state_dim)
        self.gate_proj = nn.Linear(input_dim, state_dim)
        self.log_decay = nn.Parameter(torch.zeros(state_dim))
        self.summary_head = nn.Linear(state_dim, state_dim)
        self.retrieval_hint_head = nn.Linear(state_dim, state_dim)

    def forward(self, repo_stream: torch.Tensor, mask: torch.Tensor | None = None) -> dict[str, torch.Tensor | str | bool]:
        stream = repo_stream.float()
        batch, steps, _ = stream.shape
        state = stream.new_zeros(batch, self.log_decay.numel())
        sequence: list[torch.Tensor] = []
        decay = torch.sigmoid(self.log_decay).view(1, -1)
        for index in range(steps):
            candidate = torch.tanh(self.input_proj(stream[:, index]))
            gate = torch.sigmoid(self.gate_proj(stream[:, index]))
            next_state = decay * state + gate * candidate
            if mask is not None:
                active = mask[:, index].to(dtype=stream.dtype).unsqueeze(-1)
                state = active * next_state + (1.0 - active) * state
            else:
                state = next_state
            sequence.append(state)
        states = torch.stack(sequence, dim=1) if sequence else stream.new_zeros(batch, 0, state.shape[-1])
        return {
            "compressed_repo_state": state,
            "long_context_summary": self.summary_head(state),
            "retrieval_hints": self.retrieval_hint_head(state),
            "sequence_states": states,
            "state_vector_kind": self.state_vector_kind,
            "uses_true_mamba_selective_scan": False,
            "fallback_used": False,
        }


class GNNRepoGraphEncoder(nn.Module):
    """Message-passing encoder for repo/call/import/test/dependency graphs."""

    def __init__(
        self,
        node_feature_dim: int,
        hidden_dim: int,
        node_type_count: int,
        edge_type_count: int,
        *,
        layers: int = 2,
    ) -> None:
        super().__init__()
        if min(node_feature_dim, hidden_dim, node_type_count, edge_type_count, layers) <= 0:
            raise ValueError("all dimensions and layers must be positive")
        self.node_proj = nn.Linear(node_feature_dim, hidden_dim)
        self.node_type_embedding = nn.Embedding(node_type_count, hidden_dim)
        self.edge_type_embedding = nn.Embedding(edge_type_count, hidden_dim)
        self.message = nn.Linear(hidden_dim * 2, hidden_dim)
        self.update = nn.GRUCell(hidden_dim, hidden_dim)
        self.layers = int(layers)
        self.binding_head = nn.Linear(hidden_dim, 1)
        self.edit_target_head = nn.Linear(hidden_dim, 1)
        self.impacted_test_head = nn.Linear(hidden_dim, 1)
        self.risk_head = nn.Linear(hidden_dim, 1)

    def forward(
        self,
        node_features: torch.Tensor,
        node_type_ids: torch.Tensor,
        edge_index: torch.Tensor,
        edge_type_ids: torch.Tensor,
        graph_ids: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        if edge_index.shape[0] != 2:
            raise ValueError("edge_index must have shape [2, edges]")
        hidden = self.node_proj(node_features.float()) + self.node_type_embedding(node_type_ids.long())
        src, dst = edge_index.long()
        for _ in range(self.layers):
            aggregate = hidden.new_zeros(hidden.shape)
            if src.numel() > 0:
                edge_hidden = self.edge_type_embedding(edge_type_ids.long())
                messages = torch.tanh(self.message(torch.cat([hidden[src], edge_hidden], dim=-1)))
                aggregate.index_add_(0, dst, messages)
            hidden = self.update(aggregate, hidden)
        if graph_ids is None:
            graph_ids = hidden.new_zeros(hidden.shape[0], dtype=torch.long)
        graph_count = int(graph_ids.max().item()) + 1 if graph_ids.numel() else 1
        graph_embeddings = hidden.new_zeros(graph_count, hidden.shape[-1])
        counts = hidden.new_zeros(graph_count, 1)
        graph_embeddings.index_add_(0, graph_ids.long(), hidden)
        counts.index_add_(0, graph_ids.long(), torch.ones(hidden.shape[0], 1, device=hidden.device, dtype=hidden.dtype))
        graph_embeddings = graph_embeddings / counts.clamp_min(1.0)
        return {
            "node_embeddings": hidden,
            "graph_embeddings": graph_embeddings,
            "binding_candidates": self.binding_head(hidden).squeeze(-1),
            "edit_targets": self.edit_target_head(hidden).squeeze(-1),
            "impacted_tests": self.impacted_test_head(hidden).squeeze(-1),
            "risk_propagation": torch.sigmoid(self.risk_head(hidden)).squeeze(-1),
        }


class EncoderOnlyRetrieverScorer(nn.Module):
    """Bi-encoder with an optional cross-encoder-style pair scorer."""

    def __init__(self, input_dim: int, embedding_dim: int) -> None:
        super().__init__()
        if min(input_dim, embedding_dim) <= 0:
            raise ValueError("input_dim and embedding_dim must be positive")
        self.query_head = nn.Linear(input_dim, embedding_dim, bias=False)
        self.doc_head = nn.Linear(input_dim, embedding_dim, bias=False)
        self.cross_head = nn.Sequential(
            nn.Linear(embedding_dim * 4, embedding_dim),
            nn.GELU(),
            nn.Linear(embedding_dim, 1),
        )

    def forward(self, query_features: torch.Tensor, doc_features: torch.Tensor) -> dict[str, torch.Tensor]:
        query = F.normalize(self.query_head(query_features.float()), dim=-1)
        doc = F.normalize(self.doc_head(doc_features.float()), dim=-1)
        bi_scores = query @ doc.transpose(0, 1)
        pair_query = query[:, None, :].expand(-1, doc.shape[0], -1)
        pair_doc = doc[None, :, :].expand(query.shape[0], -1, -1)
        cross_features = torch.cat([pair_query, pair_doc, pair_query * pair_doc, torch.abs(pair_query - pair_doc)], dim=-1)
        cross_scores = self.cross_head(cross_features).squeeze(-1)
        return {
            "top_k_scores": bi_scores + cross_scores,
            "bi_encoder_scores": bi_scores,
            "cross_encoder_scores": cross_scores,
            "evidence_confidence": torch.sigmoid((bi_scores + cross_scores).max(dim=-1).values),
        }


class DenoiserMaskedLM(nn.Module):
    """Masked language model for short repair/infill routes."""

    def __init__(self, vocab_size: int, hidden_dim: int, *, layers: int = 2, heads: int = 2, max_positions: int = 512) -> None:
        super().__init__()
        if min(vocab_size, hidden_dim, layers, heads, max_positions) <= 0:
            raise ValueError("all dimensions must be positive")
        self.token_embedding = nn.Embedding(vocab_size, hidden_dim, padding_idx=0)
        self.position_embedding = nn.Embedding(max_positions, hidden_dim)
        encoder_layer = nn.TransformerEncoderLayer(hidden_dim, heads, hidden_dim * 4, batch_first=True)
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=layers)
        self.lm_head = nn.Linear(hidden_dim, vocab_size)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        positions = torch.arange(input_ids.shape[1], device=input_ids.device).unsqueeze(0)
        hidden = self.token_embedding(input_ids) + self.position_embedding(positions)
        padding_mask = None if attention_mask is None else ~attention_mask.bool()
        encoded = self.encoder(hidden, src_key_padding_mask=padding_mask)
        return {"cleaned_output_logits": self.lm_head(encoded), "denoise_hidden": encoded}


class DiffusionIterativeRepair(nn.Module):
    """Verifier-conditioned iterative residual denoiser for candidate embeddings."""

    def __init__(self, state_dim: int, condition_dim: int, *, max_steps: int = 16) -> None:
        super().__init__()
        if min(state_dim, condition_dim, max_steps) <= 0:
            raise ValueError("state_dim, condition_dim, and max_steps must be positive")
        self.step_embedding = nn.Embedding(max_steps, state_dim)
        self.condition_proj = nn.Linear(condition_dim, state_dim)
        self.denoiser = nn.Sequential(
            nn.LayerNorm(state_dim * 3),
            nn.Linear(state_dim * 3, state_dim * 2),
            nn.GELU(),
            nn.Linear(state_dim * 2, state_dim),
        )
        self.score_head = nn.Linear(state_dim, 1)
        self.max_steps = int(max_steps)

    def forward(self, noisy_candidate: torch.Tensor, condition: torch.Tensor, step_ids: torch.Tensor) -> dict[str, torch.Tensor]:
        steps = step_ids.clamp(0, self.max_steps - 1).long()
        cond = self.condition_proj(condition.float())
        step = self.step_embedding(steps)
        residual = self.denoiser(torch.cat([noisy_candidate.float(), cond, step], dim=-1))
        refined = noisy_candidate.float() + residual
        return {"refined_candidate": refined, "trajectory_scores": self.score_head(refined).squeeze(-1)}

    def iterative_refine(self, candidate: torch.Tensor, condition: torch.Tensor, steps: int) -> torch.Tensor:
        refined = candidate
        for index in range(min(int(steps), self.max_steps)):
            step_ids = torch.full((candidate.shape[0],), index, device=candidate.device, dtype=torch.long)
            refined = self(refined, condition, step_ids)["refined_candidate"]
        return refined


class AutoencoderCompressor(nn.Module):
    """Compress state/diff/log features and expose reconstruction anomaly."""

    def __init__(self, input_dim: int, latent_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if min(input_dim, latent_dim, hidden_dim) <= 0:
            raise ValueError("input_dim, latent_dim, and hidden_dim must be positive")
        self.encoder = nn.Sequential(nn.LayerNorm(input_dim), nn.Linear(input_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, latent_dim))
        self.decoder = nn.Sequential(nn.Linear(latent_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, input_dim))

    def forward(self, features: torch.Tensor) -> dict[str, torch.Tensor]:
        latent = self.encoder(features.float())
        reconstruction = self.decoder(latent)
        error = F.mse_loss(reconstruction, features.float(), reduction="none").mean(dim=-1)
        return {"latent_state": latent, "reconstruction": reconstruction, "reconstruction_error": error, "anomaly_score": error}


class EnergyRewardModel(nn.Module):
    """Verifier-aware patch energy/reward scorer."""

    def __init__(self, repo_dim: int, patch_dim: int, verifier_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if min(repo_dim, patch_dim, verifier_dim, hidden_dim) <= 0:
            raise ValueError("all dimensions must be positive")
        self.trunk = nn.Sequential(
            nn.LayerNorm(repo_dim + patch_dim + verifier_dim),
            nn.Linear(repo_dim + patch_dim + verifier_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
        )
        self.energy_head = nn.Linear(hidden_dim, 1)
        self.reward_head = nn.Linear(hidden_dim, 1)

    def forward(self, repo_state: torch.Tensor, candidate_patch: torch.Tensor, verifier_signal: torch.Tensor) -> dict[str, torch.Tensor]:
        hidden = self.trunk(torch.cat([repo_state.float(), candidate_patch.float(), verifier_signal.float()], dim=-1))
        return {
            "candidate_energy": self.energy_head(hidden).squeeze(-1),
            "reward_score": torch.sigmoid(self.reward_head(hidden)).squeeze(-1),
            "preference_embedding": hidden,
        }


class AdversarialHardNegativeGAN(nn.Module):
    """Generator/discriminator pair for quarantine-gated hard negative rows."""

    def __init__(self, noise_dim: int, context_dim: int, example_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if min(noise_dim, context_dim, example_dim, hidden_dim) <= 0:
            raise ValueError("all dimensions must be positive")
        self.generator = nn.Sequential(
            nn.Linear(noise_dim + context_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, example_dim),
        )
        self.discriminator = nn.Sequential(
            nn.Linear(example_dim + context_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, 1),
        )

    def generate(self, noise: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        return self.generator(torch.cat([noise.float(), context.float()], dim=-1))

    def discriminate(self, examples: torch.Tensor, context: torch.Tensor) -> torch.Tensor:
        return self.discriminator(torch.cat([examples.float(), context.float()], dim=-1)).squeeze(-1)

    def forward(self, noise: torch.Tensor, context: torch.Tensor) -> dict[str, torch.Tensor]:
        hard_negative = self.generate(noise, context)
        return {
            "hard_negative_rows": hard_negative,
            "adversarial_shortcut_logits": self.discriminate(hard_negative, context),
        }


class LinearChainCRF(nn.Module):
    """Linear-chain CRF sequence labeler with NLL and Viterbi decoding."""

    def __init__(self, num_labels: int) -> None:
        super().__init__()
        if num_labels <= 0:
            raise ValueError("num_labels must be positive")
        self.num_labels = int(num_labels)
        self.start = nn.Parameter(torch.zeros(num_labels))
        self.end = nn.Parameter(torch.zeros(num_labels))
        self.transitions = nn.Parameter(torch.zeros(num_labels, num_labels))

    def neg_log_likelihood(self, emissions: torch.Tensor, labels: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        return (self._log_partition(emissions, mask) - self._gold_score(emissions, labels, mask)).mean()

    def _gold_score(self, emissions: torch.Tensor, labels: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        labels = labels.long()
        mask = mask.bool()
        batch, steps, _ = emissions.shape
        score = self.start[labels[:, 0]] + emissions[:, 0].gather(1, labels[:, :1]).squeeze(1)
        score = torch.where(mask[:, 0], score, torch.zeros_like(score))
        for index in range(1, steps):
            transition = self.transitions[labels[:, index - 1], labels[:, index]]
            emit = emissions[:, index].gather(1, labels[:, index:index + 1]).squeeze(1)
            score = score + torch.where(mask[:, index], transition + emit, torch.zeros_like(score))
        lengths = mask.long().sum(dim=1).clamp_min(1) - 1
        last_labels = labels.gather(1, lengths.unsqueeze(1)).squeeze(1)
        return score + self.end[last_labels]

    def _log_partition(self, emissions: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        mask = mask.bool()
        score = self.start + emissions[:, 0]
        score = torch.where(mask[:, :1], score, torch.zeros_like(score))
        for index in range(1, emissions.shape[1]):
            next_score = torch.logsumexp(
                score.unsqueeze(2) + self.transitions.unsqueeze(0) + emissions[:, index].unsqueeze(1),
                dim=1,
            )
            score = torch.where(mask[:, index:index + 1], next_score, score)
        return torch.logsumexp(score + self.end, dim=1)

    def viterbi_decode(self, emissions: torch.Tensor, mask: torch.Tensor) -> list[list[int]]:
        mask = mask.bool()
        score = self.start + emissions[:, 0]
        backpointers: list[torch.Tensor] = []
        for index in range(1, emissions.shape[1]):
            candidate = score.unsqueeze(2) + self.transitions.unsqueeze(0)
            best_score, best_path = candidate.max(dim=1)
            next_score = best_score + emissions[:, index]
            score = torch.where(mask[:, index:index + 1], next_score, score)
            backpointers.append(best_path)
        paths: list[list[int]] = []
        for batch_index in range(emissions.shape[0]):
            length = int(mask[batch_index].long().sum().item())
            if length <= 0:
                paths.append([])
                continue
            last = int((score[batch_index] + self.end).argmax().item())
            path = [last]
            for pointer in reversed(backpointers[:max(0, length - 1)]):
                last = int(pointer[batch_index, last].item())
                path.append(last)
            paths.append(list(reversed(path)))
        return paths


class CRFHMMSequenceLabeler(nn.Module):
    """Emission network plus CRF for structured line/event labeling."""

    def __init__(self, input_dim: int, hidden_dim: int, num_labels: int) -> None:
        super().__init__()
        if min(input_dim, hidden_dim, num_labels) <= 0:
            raise ValueError("input_dim, hidden_dim, and num_labels must be positive")
        self.emitter = nn.Sequential(nn.Linear(input_dim, hidden_dim), nn.GELU(), nn.Linear(hidden_dim, num_labels))
        self.crf = LinearChainCRF(num_labels)

    def forward(self, sequence_features: torch.Tensor, mask: torch.Tensor) -> dict[str, torch.Tensor | list[list[int]]]:
        emissions = self.emitter(sequence_features.float())
        return {"emissions": emissions, "segment_labels": self.crf.viterbi_decode(emissions, mask)}

    def loss(self, sequence_features: torch.Tensor, labels: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
        return self.crf.neg_log_likelihood(self.emitter(sequence_features.float()), labels, mask)


class BayesianCalibration(nn.Module):
    """Temperature/evidence calibration head for abstention decisions."""

    def __init__(self, evidence_dim: int = 0) -> None:
        super().__init__()
        self.log_temperature = nn.Parameter(torch.zeros(()))
        self.evidence_bias = nn.Linear(evidence_dim, 1) if evidence_dim > 0 else None

    def forward(self, logits: torch.Tensor, evidence_state: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        temperature = F.softplus(self.log_temperature) + 1e-4
        adjusted = logits.float() / temperature
        if self.evidence_bias is not None:
            if evidence_state is None:
                raise ValueError("evidence_state is required when evidence_dim > 0")
            adjusted = adjusted + self.evidence_bias(evidence_state.float())
        probs = torch.softmax(adjusted, dim=-1)
        confidence = probs.max(dim=-1).values
        entropy = -(probs * probs.clamp_min(1e-8).log()).sum(dim=-1)
        risk = 1.0 - confidence
        interval_width = torch.sqrt((risk * confidence).clamp_min(0.0))
        return {
            "calibrated_logits": adjusted,
            "calibrated_probs": probs,
            "calibrated_confidence": confidence,
            "abstain_threshold": risk,
            "risk_interval": torch.stack([risk - interval_width, risk + interval_width], dim=-1).clamp(0.0, 1.0),
            "entropy": entropy,
        }


class LoRAExpert(nn.Module):
    def __init__(self, input_dim: int, output_dim: int, rank: int) -> None:
        super().__init__()
        self.down = nn.Linear(input_dim, rank, bias=False)
        self.up = nn.Linear(rank, output_dim, bias=False)
        nn.init.zeros_(self.up.weight)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.up(self.down(x))


class MoELoRAAdapters(nn.Module):
    """Mixture of low-rank adapters routed by task/repo/language features."""

    def __init__(self, input_dim: int, output_dim: int, expert_count: int, rank: int) -> None:
        super().__init__()
        if min(input_dim, output_dim, expert_count, rank) <= 0:
            raise ValueError("all dimensions must be positive")
        self.base = nn.Linear(input_dim, output_dim)
        self.router = nn.Linear(input_dim, expert_count)
        self.experts = nn.ModuleList([LoRAExpert(input_dim, output_dim, rank) for _ in range(expert_count)])

    def forward(self, task_embedding: torch.Tensor) -> dict[str, torch.Tensor]:
        x = task_embedding.float()
        route_logits = self.router(x)
        weights = torch.softmax(route_logits, dim=-1)
        deltas = torch.stack([expert(x) for expert in self.experts], dim=1)
        mixed_delta = (weights.unsqueeze(-1) * deltas).sum(dim=1)
        return {
            "expert_route_logits": route_logits,
            "adapter_weights": weights,
            "adapter_id": weights.argmax(dim=-1),
            "specialist_logits": self.base(x) + mixed_delta,
        }


class RLBanditController(nn.Module):
    """Contextual bandit for action/test selection under budget."""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int) -> None:
        super().__init__()
        if min(state_dim, action_dim, hidden_dim) <= 0:
            raise ValueError("state_dim, action_dim, and hidden_dim must be positive")
        self.state_proj = nn.Linear(state_dim, hidden_dim)
        self.action_proj = nn.Linear(action_dim, hidden_dim)
        self.score_head = nn.Linear(hidden_dim, 1)
        self.stop_head = nn.Linear(hidden_dim, 2)

    def forward(self, state: torch.Tensor, available_actions: torch.Tensor, action_mask: torch.Tensor | None = None) -> dict[str, torch.Tensor]:
        state_hidden = self.state_proj(state.float())[:, None, :]
        action_hidden = self.action_proj(available_actions.float())
        hidden = torch.tanh(state_hidden + action_hidden)
        logits = self.score_head(hidden).squeeze(-1)
        if action_mask is not None:
            logits = logits.masked_fill(~action_mask.bool(), torch.finfo(logits.dtype).min)
        pooled = hidden.mean(dim=1)
        return {
            "next_action_policy_logits": logits,
            "next_action_policy": torch.softmax(logits, dim=-1),
            "test_selection": logits.argmax(dim=-1),
            "continue_or_stop_logits": self.stop_head(pooled),
        }


class WorldModelCounterfactual(nn.Module):
    """Predict consequences of candidate actions before execution."""

    def __init__(self, state_dim: int, action_dim: int, hidden_dim: int, verifier_classes: int) -> None:
        super().__init__()
        if min(state_dim, action_dim, hidden_dim, verifier_classes) <= 0:
            raise ValueError("all dimensions must be positive")
        self.trunk = nn.Sequential(
            nn.LayerNorm(state_dim + action_dim),
            nn.Linear(state_dim + action_dim, hidden_dim),
            nn.GELU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.GELU(),
        )
        self.delta_head = nn.Linear(hidden_dim, state_dim)
        self.verifier_head = nn.Linear(hidden_dim, verifier_classes)
        self.risk_head = nn.Linear(hidden_dim, 1)

    def forward(self, repo_state: torch.Tensor, candidate_action: torch.Tensor) -> dict[str, torch.Tensor]:
        hidden = self.trunk(torch.cat([repo_state.float(), candidate_action.float()], dim=-1))
        return {
            "predicted_next_state": repo_state.float() + self.delta_head(hidden),
            "expected_verifier_result": self.verifier_head(hidden),
            "counterfactual_risk": torch.sigmoid(self.risk_head(hidden)).squeeze(-1),
            "predicted_failure_modes": hidden,
        }


@dataclass(frozen=True)
class SymbolicVerifierResult:
    name: str
    passed: bool
    failure_log: str = ""
    repair_signal: str = ""


class SymbolicVerifierSuite:
    """Exact local checks with no learned confidence or acceptance authority."""

    def __init__(self) -> None:
        self._checks: dict[str, Callable[[str], SymbolicVerifierResult]] = {
            "python_ast_parse": self.python_ast_parse,
        }

    def register(self, name: str, check: Callable[[str], SymbolicVerifierResult]) -> None:
        if not name:
            raise ValueError("verifier name is required")
        self._checks[name] = check

    def run(self, candidate_patch: str, checks: Iterable[str] | None = None) -> dict[str, SymbolicVerifierResult]:
        selected = list(checks) if checks is not None else list(self._checks)
        missing = [name for name in selected if name not in self._checks]
        if missing:
            raise KeyError(f"unknown verifier checks: {missing}")
        return {name: self._checks[name](candidate_patch) for name in selected}

    @staticmethod
    def python_ast_parse(candidate_patch: str) -> SymbolicVerifierResult:
        try:
            ast.parse(candidate_patch)
        except SyntaxError as exc:
            return SymbolicVerifierResult(
                name="python_ast_parse",
                passed=False,
                failure_log=f"{exc.__class__.__name__}: {exc.msg}",
                repair_signal="repair_python_syntax",
            )
        return SymbolicVerifierResult(name="python_ast_parse", passed=True)


MODEL_FAMILY_CLASSES: Mapping[str, type] = {
    "ngram_markov": NGramMarkovPrior,
    "linear_tree_mlp_heads": LinearTreeMLPHeads,
    "rnn_lstm_gru_trace": RNNTraceCompressor,
    "state_space_mamba": MambaRepoStateCompressor,
    "gnn_repo_graph": GNNRepoGraphEncoder,
    "encoder_only_retriever": EncoderOnlyRetrieverScorer,
    "encoder_decoder_seq2seq": AgentKernelLiteTransformerSeq2Seq,
    "decoder_only_causal": RecurrentGemmaMaintainerModel,
    "denoiser_masked_lm": DenoiserMaskedLM,
    "diffusion_iterative_repair": DiffusionIterativeRepair,
    "autoencoder_compressor": AutoencoderCompressor,
    "energy_reward_model": EnergyRewardModel,
    "gan_adversarial_generator": AdversarialHardNegativeGAN,
    "crf_hmm_sequence_labeler": CRFHMMSequenceLabeler,
    "bayesian_calibration": BayesianCalibration,
    "moe_lora_adapters": MoELoRAAdapters,
    "rl_bandit_controller": RLBanditController,
    "world_model_counterfactual": WorldModelCounterfactual,
    "symbolic_verifiers": SymbolicVerifierSuite,
}

MODEL_FAMILY_IMPLEMENTATIONS: Mapping[str, str] = {
    family: implementation.__name__
    for family, implementation in MODEL_FAMILY_CLASSES.items()
}


def get_model_family_class(model_family: str) -> type:
    """Resolve a registry model-family id to its implementation class."""

    try:
        return MODEL_FAMILY_CLASSES[str(model_family)]
    except KeyError as exc:
        known = ", ".join(sorted(MODEL_FAMILY_CLASSES))
        raise KeyError(f"unknown model family {model_family!r}; known families: {known}") from exc


def build_model_family(model_family: str, **kwargs: object) -> object:
    """Instantiate a model-family implementation from registry-style config."""

    return get_model_family_class(model_family)(**kwargs)
