from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def evaluate_memory(memory: dict[str, Any], *, min_relevance: float = 0.55, max_staleness_days: int = 90) -> dict[str, Any]:
    memory_id = str(memory.get("memory_id") or memory.get("id") or "unknown_memory")
    relevance = float(memory.get("relevance_score", 0.0))
    staleness_days = int(memory.get("staleness_days", 0))
    duplicate_of = memory.get("duplicate_of")
    contamination = bool(memory.get("memory_contamination_flag") or memory.get("locked_eval_source") or memory.get("hidden_eval_source"))
    has_source = bool(memory.get("source_id") or memory.get("lineage_hash"))
    reasons: list[str] = []
    if relevance < min_relevance:
        reasons.append("low_relevance")
    if staleness_days > max_staleness_days:
        reasons.append("stale_memory")
    if duplicate_of:
        reasons.append("duplicate_memory")
    if contamination:
        reasons.append("memory_contamination")
    if not has_source:
        reasons.append("missing_memory_lineage")
    if contamination:
        route = "BLOCK_MEMORY_CONTAMINATION"
    elif duplicate_of or staleness_days > max_staleness_days or relevance < min_relevance or not has_source:
        route = "HOLD_MEMORY_REVIEW"
    else:
        route = "PASS_MEMORY_RETRIEVAL"
    quality = max(0.0, min(1.0, relevance - max(0, staleness_days - max_staleness_days) * 0.002 - (0.2 if duplicate_of else 0.0) - (0.5 if contamination else 0.0) - (0.1 if not has_source else 0.0)))
    return {
        "memory_id": memory_id,
        "memory_route": route,
        "memory_hit_quality": round(quality, 4),
        "relevance_score": relevance,
        "staleness_days": staleness_days,
        "duplicate_of": duplicate_of,
        "memory_contamination_flag": contamination,
        "skill_reuse_score": round(quality if route == "PASS_MEMORY_RETRIEVAL" else quality * 0.5, 4),
        "blocked": route == "BLOCK_MEMORY_CONTAMINATION",
        "needs_review": route == "HOLD_MEMORY_REVIEW",
        "reasons": reasons,
    }


def evaluate_memories(memories: list[dict[str, Any]]) -> dict[str, Any]:
    records = [evaluate_memory(memory) for memory in memories]
    route_counts = Counter(record["memory_route"] for record in records)
    return {
        "memories": len(memories),
        "records": records,
        "metrics": {
            "memories": len(memories),
            "pass_memories": route_counts.get("PASS_MEMORY_RETRIEVAL", 0),
            "review_memories": route_counts.get("HOLD_MEMORY_REVIEW", 0),
            "blocked_memories": route_counts.get("BLOCK_MEMORY_CONTAMINATION", 0),
            "route_counts": dict(route_counts),
            "avg_skill_reuse_score": round(sum(record["skill_reuse_score"] for record in records) / len(records), 4) if records else 0.0,
        },
    }


def read_json_or_jsonl(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text.startswith("["):
        data = json.loads(text)
        return data if isinstance(data, list) else []
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate retrieved memories for relevance, staleness, duplication, lineage, and contamination.")
    parser.add_argument("memories", type=Path)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    card = evaluate_memories(read_json_or_jsonl(args.memories))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
