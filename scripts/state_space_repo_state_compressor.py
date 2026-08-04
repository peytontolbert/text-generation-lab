from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import log1p, sqrt
from typing import Any, Iterable

try:
    import torch
    import torch.nn as nn
except Exception:  # pragma: no cover - exercised in lightweight audit environments without torch.nn
    torch = None  # type: ignore[assignment]
    nn = None  # type: ignore[assignment]

EVENT_TYPES = [
    "source",
    "test",
    "error",
    "symbol",
    "dependency",
    "runtime",
    "patch",
    "memory",
    "doc",
    "other",
]
EVENT_INDEX = {name: index for index, name in enumerate(EVENT_TYPES)}
LEAK_MARKERS = ("target_body", "oracle", "expected_answer", "clean_state", "decoder_text")


@dataclass(frozen=True)
class RepoStreamEvent:
    event_id: str
    event_type: str
    text: str
    importance: float = 0.0
    retrieval_score: float = 0.0
    grounding_score: float = 0.0
    recency: float = 0.0
    token_len: int | None = None
    metadata: dict[str, Any] | None = None


if nn is not None:
    class LearnedRepoStateEncoder(nn.Module):
        """Trainable encoder for model-visible repository state streams.

        The input is tokenized event text in chronological order. Event type, score,
        role, status, hash, and ranking metadata are intentionally excluded from the
        forward path; those remain audit-only signals outside the model.
        """

        def __init__(self, *, vocab_size: int, embedding_dim: int = 128, hidden_dim: int = 128, state_dim: int = 128) -> None:
            super().__init__()
            if vocab_size <= 0 or embedding_dim <= 0 or hidden_dim <= 0 or state_dim <= 0:
                raise ValueError("learned repo-state encoder dimensions must be positive")
            self.embedding = nn.Embedding(vocab_size, embedding_dim, padding_idx=0)
            self.event_encoder = nn.GRU(embedding_dim, hidden_dim, batch_first=True)
            self.stream_encoder = nn.GRU(hidden_dim, hidden_dim, batch_first=True)
            self.projection = nn.Sequential(nn.LayerNorm(hidden_dim), nn.Linear(hidden_dim, state_dim))
            self.state_dim = int(state_dim)

        def forward(self, event_token_ids: torch.Tensor, event_mask: torch.Tensor | None = None) -> torch.Tensor:
            if event_token_ids.dim() != 3:
                raise ValueError("event_token_ids must have shape [batch, events, tokens]")
            batch, events, tokens = event_token_ids.shape
            if events <= 0 or tokens <= 0:
                return torch.zeros(batch, self.state_dim, device=event_token_ids.device)
            flat_ids = event_token_ids.reshape(batch * events, tokens)
            flat_emb = self.embedding(flat_ids)
            _, event_hidden = self.event_encoder(flat_emb)
            event_vectors = event_hidden[-1].reshape(batch, events, -1)
            if event_mask is not None:
                event_vectors = event_vectors * event_mask.to(dtype=event_vectors.dtype).unsqueeze(-1)
            _, stream_hidden = self.stream_encoder(event_vectors)
            return self.projection(stream_hidden[-1])
else:
    class LearnedRepoStateEncoder:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise ImportError("LearnedRepoStateEncoder requires a torch installation with torch.nn")

def _tokenize_repo_events_for_model(
    events: list[RepoStreamEvent],
    *,
    tokenizer: Any,
    max_events: int,
    max_event_tokens: int,
    device: torch.device | str | None = None,
) -> tuple[torch.Tensor, torch.Tensor, list[dict[str, Any]]]:
    if max_events <= 0 or max_event_tokens <= 0:
        raise ValueError("max_events and max_event_tokens must be positive")
    pad_id = int(getattr(tokenizer, "pad_id", 0))
    rows: list[list[int]] = []
    dropped: list[dict[str, Any]] = []
    for event in events:
        flags = contamination_flags(event)
        if flags:
            dropped.append({"event_id": event.event_id, "reason": "contamination", "flags": flags})
            continue
        text = event.text.strip()
        if not text:
            dropped.append({"event_id": event.event_id, "reason": "empty_text"})
            continue
        token_ids = [int(idx) for idx in tokenizer.encode(text, max_length=max_event_tokens)]
        if not token_ids:
            dropped.append({"event_id": event.event_id, "reason": "empty_tokenization"})
            continue
        token_ids = token_ids[:max_event_tokens]
        if len(token_ids) < max_event_tokens:
            token_ids.extend([pad_id] * (max_event_tokens - len(token_ids)))
        rows.append(token_ids)
        if len(rows) >= max_events:
            break
    if not rows:
        tensor = torch.full((1, 1, max_event_tokens), pad_id, dtype=torch.long, device=device)
        mask = torch.zeros((1, 1), dtype=torch.bool, device=device)
        return tensor, mask, dropped
    tensor = torch.tensor(rows, dtype=torch.long, device=device).unsqueeze(0)
    mask = tensor.ne(pad_id).any(dim=-1)
    return tensor, mask, dropped


def encode_repo_state_with_learned_encoder(
    events: Iterable[dict[str, Any] | RepoStreamEvent],
    *,
    tokenizer: Any,
    encoder: LearnedRepoStateEncoder,
    max_events: int = 64,
    max_event_tokens: int = 96,
    detach: bool = True,
) -> dict[str, Any]:
    if torch is None or nn is None:
        raise ImportError("learned repo-state encoding requires a torch installation with torch.nn")
    parsed = [row if isinstance(row, RepoStreamEvent) else event_from_dict(row) for row in events]
    device = next(encoder.parameters()).device
    token_ids, event_mask, dropped = _tokenize_repo_events_for_model(
        parsed,
        tokenizer=tokenizer,
        max_events=max_events,
        max_event_tokens=max_event_tokens,
        device=device,
    )
    state = encoder(token_ids, event_mask)
    state_for_card = state.detach() if detach else state
    return {
        "passed": bool(event_mask.any().item()),
        "state_dim": int(state.shape[-1]),
        "events_seen": len(parsed),
        "events_encoded": int(event_mask.sum().item()),
        "events_dropped": len(dropped),
        "state_tensor": state if not detach else None,
        "state_vector": state_for_card.squeeze(0).float().cpu().tolist(),
        "state_vector_kind": "learned_repo_state_embedding",
        "model_visible_state_allowed": True,
        "replacement_required_for_training": False,
        "dropped_events": dropped,
        "compressed_repo_state": {
            "state_vector_kind": "learned_repo_state_embedding",
            "model_visible_state_allowed": True,
            "replacement_required_for_training": False,
            "encoded_event_count": int(event_mask.sum().item()),
        },
        "authority": {
            "model_execution": True,
            "training": True,
            "runtime": False,
            "source_body_emission": False,
        },
    }


def stable_hash(text: str) -> str:
    return sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    return max(1, (len(text.split()) * 4 + 2) // 3)


def event_from_dict(row: dict[str, Any]) -> RepoStreamEvent:
    text = str(row.get("text") or row.get("content") or row.get("span") or row.get("message") or "")
    event_type = str(row.get("event_type") or row.get("source_type") or row.get("type") or "other")
    if event_type not in EVENT_INDEX:
        event_type = "other"
    return RepoStreamEvent(
        event_id=str(row.get("event_id") or row.get("item_id") or row.get("row_id") or stable_hash(text)),
        event_type=event_type,
        text=text,
        importance=float(row.get("importance") or 0.0),
        retrieval_score=float(row.get("retrieval_score") or row.get("score") or 0.0),
        grounding_score=float(row.get("grounding_score") or row.get("source_grounding_score") or 0.0),
        recency=float(row.get("recency") or row.get("freshness_score") or 0.0),
        token_len=int(row["token_len"]) if row.get("token_len") is not None else None,
        metadata={k: v for k, v in row.items() if k not in {"text", "content", "span", "message"}},
    )


def contamination_flags(event: RepoStreamEvent) -> list[str]:
    haystack = " ".join([event.event_id, event.event_type, event.text, str(event.metadata or {})]).lower()
    return sorted({marker for marker in LEAK_MARKERS if marker in haystack})


def event_score(event: RepoStreamEvent) -> float:
    type_bonus = 0.25 if event.event_type in {"source", "test", "error", "symbol"} else 0.0
    return (
        type_bonus
        + 0.35 * event.importance
        + 0.25 * event.retrieval_score
        + 0.25 * event.grounding_score
        + 0.15 * event.recency
    )


def event_features(event: RepoStreamEvent, *, dim: int) -> list[float]:
    vec = [0.0] * dim
    idx = EVENT_INDEX.get(event.event_type, EVENT_INDEX["other"])
    if idx < dim:
        vec[idx] = 1.0
    length_feature = log1p(event.token_len if event.token_len is not None else estimate_tokens(event.text)) / 10.0
    scalar_features = [event.importance, event.retrieval_score, event.grounding_score, event.recency, length_feature, event_score(event)]
    for offset, value in enumerate(scalar_features):
        pos = len(EVENT_TYPES) + offset
        if pos < dim:
            vec[pos] = float(value)
    # Stable lexical sketch so repeated source/log patterns affect the compressed state deterministically.
    digest = sha256(event.text.encode("utf-8")).digest()
    start = len(EVENT_TYPES) + len(scalar_features)
    for i in range(start, dim):
        byte = digest[(i - start) % len(digest)]
        vec[i] = (byte / 255.0) * 2.0 - 1.0
    return vec


def selective_scan_compress(
    events: Iterable[dict[str, Any] | RepoStreamEvent],
    *,
    state_dim: int = 32,
    decay: float = 0.82,
    max_hints: int = 8,
    token_budget: int = 512,
    as_model_input: bool = False,
    learned_encoder: LearnedRepoStateEncoder | None = None,
    tokenizer: Any | None = None,
    max_model_events: int = 64,
    max_model_event_tokens: int = 96,
) -> dict[str, Any]:
    if as_model_input:
        if learned_encoder is None or tokenizer is None:
            raise ValueError(
                "as_model_input=True requires a LearnedRepoStateEncoder and tokenizer; "
                "the deterministic audit sketch is not a model input"
            )
        return encode_repo_state_with_learned_encoder(
            events,
            tokenizer=tokenizer,
            encoder=learned_encoder,
            max_events=max_model_events,
            max_event_tokens=max_model_event_tokens,
        )
    if state_dim < len(EVENT_TYPES) + 6:
        raise ValueError("state_dim must be at least event-type count + scalar features")
    if not 0.0 <= decay < 1.0:
        raise ValueError("decay must be in [0, 1)")
    parsed = [row if isinstance(row, RepoStreamEvent) else event_from_dict(row) for row in events]
    state = [0.0] * state_dim
    accepted: list[RepoStreamEvent] = []
    dropped: list[dict[str, Any]] = []
    type_counts = {name: 0 for name in EVENT_TYPES}
    used_tokens = 0
    for step, event in enumerate(parsed):
        flags = contamination_flags(event)
        if flags:
            dropped.append({"event_id": event.event_id, "reason": "contamination", "flags": flags})
            continue
        if not event.text.strip():
            dropped.append({"event_id": event.event_id, "reason": "empty_text"})
            continue
        length = event.token_len if event.token_len is not None else estimate_tokens(event.text)
        if used_tokens + length > token_budget and event_score(event) < 0.75:
            dropped.append({"event_id": event.event_id, "reason": "budget", "token_len": length})
            continue
        features = event_features(event, dim=state_dim)
        gate = max(0.05, min(1.0, 0.25 + event_score(event)))
        state = [decay * old + gate * feat for old, feat in zip(state, features)]
        accepted.append(event)
        type_counts[event.event_type] += 1
        used_tokens += length
    norm = sqrt(sum(x * x for x in state)) or 1.0
    normalized_state = [x / norm for x in state]
    ranked = sorted(accepted, key=event_score, reverse=True)[:max_hints]
    retrieval_hints = [
        {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "score": event_score(event),
            "text_hash": stable_hash(event.text),
            "token_len": event.token_len if event.token_len is not None else estimate_tokens(event.text),
        }
        for event in ranked
    ]
    return {
        "passed": bool(accepted) and used_tokens <= max(token_budget, used_tokens),
        "state_dim": state_dim,
        "decay": decay,
        "events_seen": len(parsed),
        "events_accepted": len(accepted),
        "events_dropped": len(dropped),
        "used_tokens_estimate": used_tokens,
        "type_counts": type_counts,
        "state_vector": normalized_state,
        "state_vector_kind": "deterministic_audit_sketch_not_model_embedding",
        "model_visible_state_allowed": False,
        "replacement_required_for_training": True,
        "state_norm": sqrt(sum(x * x for x in normalized_state)),
        "retrieval_hints": retrieval_hints,
        "dropped_events": dropped,
        "compressed_repo_state": {
            "state_vector_hash": stable_hash(jsonable_vector(normalized_state)),
            "state_vector_kind": "deterministic_audit_sketch_not_model_embedding",
            "model_visible_state_allowed": False,
            "replacement_required_for_training": True,
            "dominant_event_types": sorted(type_counts, key=type_counts.get, reverse=True)[:4],
            "hint_ids": [hint["event_id"] for hint in retrieval_hints],
        },
        "authority": {
            "model_execution": False,
            "training": False,
            "runtime": False,
            "source_body_emission": False,
        },
    }


def jsonable_vector(vector: list[float]) -> str:
    return ",".join(f"{value:.6f}" for value in vector)
