from __future__ import annotations

from dataclasses import dataclass, asdict
from hashlib import sha256
from typing import Any, Iterable


HIGH_VALUE_TYPES = {"source", "test", "error", "symbol", "patch_context"}
LOW_VALUE_TYPES = {"memory", "doc", "note"}
LEAK_MARKERS = ("target_body", "oracle", "expected_answer", "clean_state", "decoder_text")


@dataclass(frozen=True)
class EvidenceItem:
    item_id: str
    text: str
    source_type: str = "source"
    token_len: int | None = None
    retrieval_score: float = 0.0
    freshness_score: float = 0.0
    grounding_score: float = 0.0
    memory_score: float = 0.0
    contamination_score: float = 0.0
    duplicate_group: str | None = None
    required: bool = False
    metadata: dict[str, Any] | None = None


def stable_text_hash(text: str) -> str:
    return sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def estimate_tokens(text: str) -> int:
    # Conservative cheap estimate for packer audits; tokenizer-specific packing can replace this later.
    return max(1, (len(text.split()) * 4 + 2) // 3)


def item_from_dict(row: dict[str, Any]) -> EvidenceItem:
    text = str(row.get("text") or row.get("content") or row.get("span") or "")
    item_id = str(row.get("item_id") or row.get("row_id") or row.get("id") or stable_text_hash(text))
    return EvidenceItem(
        item_id=item_id,
        text=text,
        source_type=str(row.get("source_type") or row.get("type") or "source"),
        token_len=int(row["token_len"]) if row.get("token_len") is not None else None,
        retrieval_score=float(row.get("retrieval_score") or row.get("bm25_score") or row.get("score") or 0.0),
        freshness_score=float(row.get("freshness_score") or 0.0),
        grounding_score=float(row.get("grounding_score") or row.get("source_grounding_score") or 0.0),
        memory_score=float(row.get("memory_score") or 0.0),
        contamination_score=float(row.get("contamination_score") or 0.0),
        duplicate_group=(str(row.get("duplicate_group")) if row.get("duplicate_group") is not None else None),
        required=bool(row.get("required", False)),
        metadata={k: v for k, v in row.items() if k not in {"text", "content", "span"}},
    )


def contamination_flags(item: EvidenceItem) -> list[str]:
    haystack = " ".join([item.item_id, item.source_type, item.text, str(item.metadata or {})]).lower()
    flags = [marker for marker in LEAK_MARKERS if marker in haystack]
    if item.contamination_score >= 0.5:
        flags.append("high_contamination_score")
    return sorted(set(flags))


def evidence_value(item: EvidenceItem) -> float:
    type_bonus = 0.15 if item.source_type in HIGH_VALUE_TYPES else (-0.10 if item.source_type in LOW_VALUE_TYPES else 0.0)
    required_bonus = 1.0 if item.required else 0.0
    contamination_penalty = 2.0 * max(0.0, min(1.0, item.contamination_score))
    return (
        required_bonus
        + type_bonus
        + 0.45 * item.retrieval_score
        + 0.25 * item.grounding_score
        + 0.15 * item.freshness_score
        + 0.10 * item.memory_score
        - contamination_penalty
    )


def dedupe_items(items: Iterable[EvidenceItem]) -> tuple[list[EvidenceItem], list[dict[str, Any]]]:
    seen: set[str] = set()
    kept: list[EvidenceItem] = []
    dropped: list[dict[str, Any]] = []
    for item in items:
        key = item.duplicate_group or stable_text_hash(item.text)
        if key in seen:
            dropped.append({"item_id": item.item_id, "reason": "duplicate", "duplicate_key": key})
            continue
        seen.add(key)
        kept.append(item)
    return kept, dropped


def lost_in_middle_order(selected: list[EvidenceItem]) -> list[EvidenceItem]:
    """Place strongest evidence at the front and back, weakest in the middle."""
    ordered = sorted(selected, key=evidence_value, reverse=True)
    front: list[EvidenceItem] = []
    back: list[EvidenceItem] = []
    middle: list[EvidenceItem] = []
    for index, item in enumerate(ordered):
        if index == 0 or index % 3 == 0:
            front.append(item)
        elif index == 1 or index % 3 == 1:
            back.append(item)
        else:
            middle.append(item)
    return front + middle + list(reversed(back))


def pack_context(
    rows: Iterable[dict[str, Any] | EvidenceItem],
    *,
    token_budget: int,
    min_required: int = 0,
) -> dict[str, Any]:
    raw_items = [row if isinstance(row, EvidenceItem) else item_from_dict(row) for row in rows]
    clean_items: list[EvidenceItem] = []
    dropped: list[dict[str, Any]] = []
    for item in raw_items:
        flags = contamination_flags(item)
        if flags:
            dropped.append({"item_id": item.item_id, "reason": "contamination", "flags": flags})
        elif not item.text.strip():
            dropped.append({"item_id": item.item_id, "reason": "empty_text"})
        else:
            clean_items.append(item)

    deduped, duplicate_drops = dedupe_items(clean_items)
    dropped.extend(duplicate_drops)

    sorted_items = sorted(deduped, key=evidence_value, reverse=True)
    selected: list[EvidenceItem] = []
    used = 0
    for item in sorted_items:
        length = item.token_len if item.token_len is not None else estimate_tokens(item.text)
        if length > token_budget and not item.required:
            dropped.append({"item_id": item.item_id, "reason": "single_item_over_budget", "token_len": length})
            continue
        if used + length <= token_budget:
            selected.append(item)
            used += length
        elif item.required:
            dropped.append({"item_id": item.item_id, "reason": "required_over_budget", "token_len": length})
        else:
            dropped.append({"item_id": item.item_id, "reason": "budget", "token_len": length})

    ordered = lost_in_middle_order(selected)
    required_selected = sum(1 for item in selected if item.required)
    packed_text = "\n\n".join(f"[{item.source_type}:{item.item_id}]\n{item.text}" for item in ordered)
    return {
        "passed": required_selected >= min_required and used <= token_budget,
        "token_budget": token_budget,
        "used_tokens_estimate": used,
        "selected_count": len(selected),
        "dropped_count": len(dropped),
        "required_selected": required_selected,
        "selected_items": [asdict(item) | {"value_score": evidence_value(item)} for item in ordered],
        "dropped_items": dropped,
        "packed_text": packed_text,
        "lost_in_middle_policy": "high_value_front_and_back",
        "authority": {
            "model_execution": False,
            "training": False,
            "runtime": False,
            "source_body_emission": False,
        },
    }


def evaluate_memory_items(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    items = [item_from_dict(row) for row in rows]
    stale = [item.item_id for item in items if item.freshness_score < 0.2 and item.source_type == "memory"]
    contaminated = [item.item_id for item in items if contamination_flags(item)]
    duplicate_keys: dict[str, list[str]] = {}
    for item in items:
        key = item.duplicate_group or stable_text_hash(item.text)
        duplicate_keys.setdefault(key, []).append(item.item_id)
    duplicates = {key: ids for key, ids in duplicate_keys.items() if len(ids) > 1}
    return {
        "rows": len(items),
        "stale_memory_ids": stale,
        "contaminated_ids": contaminated,
        "duplicate_groups": duplicates,
        "usable_memory_rows": len(items) - len(set(stale) | set(contaminated)),
    }
