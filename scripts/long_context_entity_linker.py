from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from long_context_common import extract_terms, infer_entity_type, read_jsonl, stable_id, write_json, write_jsonl


def build_entities(chunks: list[dict[str, Any]], *, min_mention_count: int = 2, max_terms_per_chunk: int = 16) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mentions: dict[str, list[dict[str, str]]] = defaultdict(list)
    for chunk in chunks:
        candidates = set(extract_terms(chunk.get("text", ""), max_terms=max_terms_per_chunk))
        meta = chunk.get("metadata", {})
        for field in ("method_terms", "benchmark_terms", "error_terms", "symbol_names"):
            value = meta.get(field)
            if isinstance(value, list):
                candidates.update(str(item).lower() for item in value if str(item).strip())
        for term in candidates:
            if len(term) < 3:
                continue
            mentions[term].append(
                {
                    "chunk_id": str(chunk["chunk_id"]),
                    "source_type": str(chunk["source_type"]),
                    "source_id": str(chunk["source_id"]),
                }
            )
    rows: list[dict[str, Any]] = []
    for term, items in sorted(mentions.items()):
        if len(items) < min_mention_count:
            continue
        source_type_counts = Counter(item["source_type"] for item in items)
        rows.append(
            {
                "entity_id": stable_id("ent", term),
                "entity_type": infer_entity_type(term, source_type_counts.keys()),
                "canonical_name": term,
                "aliases": [term],
                "mentions": [item["chunk_id"] for item in items],
                "source_type_counts": dict(sorted(source_type_counts.items())),
            }
        )
    alias_card = {
        "entity_count": len(rows),
        "min_mention_count": min_mention_count,
        "top_entities": [
            {
                "canonical_name": row["canonical_name"],
                "mention_count": len(row["mentions"]),
                "entity_type": row["entity_type"],
            }
            for row in sorted(rows, key=lambda item: (-len(item["mentions"]), item["canonical_name"]))[:50]
        ],
    }
    return rows, alias_card


def main() -> None:
    parser = argparse.ArgumentParser(description="Build conservative cross-source entity tables from long-context chunks.")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--alias-output", type=Path)
    parser.add_argument("--min-mention-count", type=int, default=2)
    args = parser.parse_args()
    entities, alias_card = build_entities(read_jsonl(args.chunks), min_mention_count=args.min_mention_count)
    write_jsonl(args.output, entities)
    write_json(args.alias_output or args.output.with_name("entity_aliases.json"), alias_card)


if __name__ == "__main__":
    main()
