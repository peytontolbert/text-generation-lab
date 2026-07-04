from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from math import log1p, sqrt
from typing import Any, Iterable

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
) -> dict[str, Any]:
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
        "state_norm": sqrt(sum(x * x for x in normalized_state)),
        "retrieval_hints": retrieval_hints,
        "dropped_events": dropped,
        "compressed_repo_state": {
            "state_vector_hash": stable_hash(jsonable_vector(normalized_state)),
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
