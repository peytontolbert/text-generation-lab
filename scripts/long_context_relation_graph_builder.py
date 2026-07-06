from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
from typing import Any

from long_context_common import read_jsonl, stable_id, write_json, write_jsonl


def build_relation_graph(chunks: list[dict[str, Any]], entities: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    chunk_by_id = {str(chunk["chunk_id"]): chunk for chunk in chunks}
    links: list[dict[str, Any]] = []
    edge_type_counts: Counter[str] = Counter()

    for entity in entities:
        entity_id = str(entity["entity_id"])
        mentions = [str(chunk_id) for chunk_id in entity.get("mentions", []) if str(chunk_id) in chunk_by_id]
        for chunk_id in mentions:
            links.append({
                "link_id": stable_id("link", entity_id, chunk_id, "chunk_mentions_entity"),
                "src": chunk_id,
                "dst": entity_id,
                "edge_type": "chunk_mentions_entity",
            })
            edge_type_counts["chunk_mentions_entity"] += 1
            links.append({
                "link_id": stable_id("link", entity_id, chunk_id, "entity_mentioned_by_chunk"),
                "src": entity_id,
                "dst": chunk_id,
                "edge_type": "entity_mentioned_by_chunk",
            })
            edge_type_counts["entity_mentioned_by_chunk"] += 1
        for i in range(len(mentions)):
            for j in range(i + 1, len(mentions)):
                a = mentions[i]
                b = mentions[j]
                links.append({
                    "link_id": stable_id("link", a, b, entity_id, "entity_co_mention"),
                    "src": a,
                    "dst": b,
                    "edge_type": "entity_co_mention",
                    "entity_id": entity_id,
                })
                edge_type_counts["entity_co_mention"] += 1

    by_doc: dict[tuple[str, str], list[str]] = {}
    for chunk in chunks:
        key = (str(chunk.get("source_id") or ""), str(chunk.get("doc_id") or ""))
        by_doc.setdefault(key, []).append(str(chunk["chunk_id"]))
    for chunk_ids in by_doc.values():
        for left, right in zip(chunk_ids, chunk_ids[1:]):
            links.append({
                "link_id": stable_id("link", left, right, "adjacent_chunk"),
                "src": left,
                "dst": right,
                "edge_type": "adjacent_chunk",
            })
            edge_type_counts["adjacent_chunk"] += 1

    by_source: dict[str, list[str]] = {}
    for chunk in chunks:
        by_source.setdefault(str(chunk.get("source_id") or ""), []).append(str(chunk["chunk_id"]))
    for source_id, chunk_ids in by_source.items():
        if len(chunk_ids) < 2:
            continue
        anchor = chunk_ids[0]
        for other in chunk_ids[1:]:
            links.append({
                "link_id": stable_id("link", source_id, anchor, other, "same_source_chunk"),
                "src": anchor,
                "dst": other,
                "edge_type": "same_source_chunk",
                "source_id": source_id,
            })
            edge_type_counts["same_source_chunk"] += 1

    summary = {
        "link_count": len(links),
        "edge_type_counts": dict(sorted(edge_type_counts.items())),
        "chunk_count": len(chunks),
        "entity_count": len(entities),
    }
    return links, summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a relation graph over chunks and entities for long-context candidate mining.")
    parser.add_argument("--chunks", type=Path, required=True)
    parser.add_argument("--entities", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    links, summary = build_relation_graph(read_jsonl(args.chunks), read_jsonl(args.entities))
    write_jsonl(args.output, links)
    write_json(args.summary_output or args.output.with_name("links_summary.json"), summary)


if __name__ == "__main__":
    main()
