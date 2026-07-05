from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, deque
from pathlib import Path
from typing import Any, Iterable, Mapping

ALLOWED_NODE_TYPES = {"skill", "source_fact", "tool_outcome", "repo_entity", "dataset_patch", "eval_trace", "concept"}
ALLOWED_EDGE_TYPES = {"supports", "derived_from", "used_tool", "touches", "verified_by", "similar_to", "blocks", "supersedes"}
BLOCK_REASONS = {"locked_eval_source", "hidden_eval_source", "contamination_risk", "raw_source_body"}


def stable_id(kind: str, value: str) -> str:
    digest = hashlib.sha256(f"{kind}:{value}".encode("utf-8")).hexdigest()[:20]
    return f"{kind}_{digest}"


def _bool(value: Any) -> bool:
    return value is True or str(value).lower() in {"1", "true", "yes"}


def _tags(value: Any) -> list[str]:
    if isinstance(value, list):
        return sorted({str(item) for item in value if str(item)})
    if isinstance(value, str) and value:
        return [value]
    return []


def _blocked(record: Mapping[str, Any]) -> list[str]:
    return sorted(reason for reason in BLOCK_REASONS if _bool(record.get(reason)))


class KnowledgeGraphMemoryStore:
    def __init__(self) -> None:
        self.nodes: dict[str, dict[str, Any]] = {}
        self.edges: dict[str, dict[str, Any]] = {}

    def upsert_node(self, record: Mapping[str, Any]) -> dict[str, Any]:
        blocked = _blocked(record)
        node_type = str(record.get("node_type", record.get("type", "")))
        if blocked:
            return {"route": "BLOCK_MEMORY_CONTAMINATION", "reasons": blocked, "node_id": None}
        if node_type not in ALLOWED_NODE_TYPES:
            return {"route": "HOLD_MEMORY_SCHEMA_REVIEW", "reasons": [f"unknown_node_type:{node_type}"], "node_id": None}
        raw_key = str(record.get("memory_key") or record.get("entity_id") or record.get("text") or record.get("label") or "")
        if not raw_key:
            return {"route": "HOLD_MEMORY_SCHEMA_REVIEW", "reasons": ["missing_memory_key"], "node_id": None}
        node_id = str(record.get("node_id") or stable_id(node_type, raw_key))
        existing = self.nodes.get(node_id, {})
        tags = sorted(set(_tags(existing.get("tags")) + _tags(record.get("tags"))))
        node = {
            "node_id": node_id,
            "node_type": node_type,
            "memory_key": raw_key,
            "label": str(record.get("label", existing.get("label", raw_key))),
            "tags": tags,
            "lineage": record.get("lineage", existing.get("lineage", {})),
            "payload": record.get("payload", existing.get("payload", {})),
            "promotion_authority": False,
        }
        self.nodes[node_id] = node
        return {"route": "PASS_MEMORY_NODE_UPSERT", "node_id": node_id, "node": node, "reasons": []}

    def upsert_edge(self, record: Mapping[str, Any]) -> dict[str, Any]:
        blocked = _blocked(record)
        edge_type = str(record.get("edge_type", record.get("relationship_type", "")))
        src = str(record.get("src", record.get("source", "")))
        dst = str(record.get("dst", record.get("target", "")))
        if blocked:
            return {"route": "BLOCK_MEMORY_CONTAMINATION", "reasons": blocked, "edge_id": None}
        if edge_type not in ALLOWED_EDGE_TYPES:
            return {"route": "HOLD_MEMORY_SCHEMA_REVIEW", "reasons": [f"unknown_edge_type:{edge_type}"], "edge_id": None}
        if not src or not dst:
            return {"route": "HOLD_MEMORY_SCHEMA_REVIEW", "reasons": ["missing_edge_endpoint"], "edge_id": None}
        if src not in self.nodes or dst not in self.nodes:
            return {"route": "HOLD_MEMORY_SCHEMA_REVIEW", "reasons": ["edge_endpoint_not_found"], "edge_id": None}
        edge_id = str(record.get("edge_id") or stable_id("edge", f"{src}:{edge_type}:{dst}"))
        edge = {
            "edge_id": edge_id,
            "src": src,
            "dst": dst,
            "edge_type": edge_type,
            "weight": float(record.get("weight", 1.0)),
            "lineage": record.get("lineage", {}),
            "promotion_authority": False,
        }
        self.edges[edge_id] = edge
        return {"route": "PASS_MEMORY_EDGE_UPSERT", "edge_id": edge_id, "edge": edge, "reasons": []}

    def query(self, *, text: str = "", tags: Iterable[str] = (), node_type: str | None = None, limit: int = 10) -> dict[str, Any]:
        query_terms = {term.lower() for term in text.split() if term}
        tag_set = {str(tag) for tag in tags}
        scored = []
        for node in self.nodes.values():
            if node_type and node["node_type"] != node_type:
                continue
            label_terms = set(str(node.get("label", "")).lower().split())
            node_tags = set(_tags(node.get("tags")))
            score = len(query_terms & label_terms) + 2 * len(tag_set & node_tags)
            if text and str(node.get("memory_key", "")).lower() == text.lower():
                score += 3
            if score > 0 or (not query_terms and not tag_set and not node_type):
                scored.append((score, node["node_id"], node))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return {
            "route": "PASS_MEMORY_RETRIEVAL" if scored else "HOLD_MEMORY_MISS",
            "results": [{"score": score, "node": node} for score, _node_id, node in scored[:limit]],
            "result_count": min(len(scored), limit),
        }

    def retrieval_path(self, src: str, dst: str, *, max_depth: int = 3) -> dict[str, Any]:
        if src not in self.nodes or dst not in self.nodes:
            return {"route": "HOLD_MEMORY_MISS", "path": [], "reasons": ["endpoint_not_found"]}
        adjacency: dict[str, list[tuple[str, str]]] = {}
        for edge in self.edges.values():
            adjacency.setdefault(edge["src"], []).append((edge["dst"], edge["edge_type"]))
        q: deque[tuple[str, list[dict[str, str]]]] = deque([(src, [{"node_id": src}] )])
        seen = {src}
        while q:
            node_id, path = q.popleft()
            if len(path) > max_depth + 1:
                continue
            if node_id == dst:
                return {"route": "PASS_MEMORY_PATH", "path": path, "reasons": []}
            for next_id, edge_type in adjacency.get(node_id, []):
                if next_id in seen:
                    continue
                seen.add(next_id)
                q.append((next_id, path + [{"edge_type": edge_type}, {"node_id": next_id}]))
        return {"route": "HOLD_MEMORY_MISS", "path": [], "reasons": ["path_not_found"]}

    def export_card(self) -> dict[str, Any]:
        node_types = Counter(node["node_type"] for node in self.nodes.values())
        edge_types = Counter(edge["edge_type"] for edge in self.edges.values())
        return {
            "nodes": list(self.nodes.values()),
            "edges": list(self.edges.values()),
            "metrics": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "node_types": dict(node_types),
                "edge_types": dict(edge_types),
                "authority_rows": 0,
            },
        }


def build_store_card(records: list[Mapping[str, Any]]) -> dict[str, Any]:
    store = KnowledgeGraphMemoryStore()
    operations = []
    for record in records:
        op = str(record.get("op", "node"))
        if op == "edge":
            operations.append(store.upsert_edge(record))
        else:
            operations.append(store.upsert_node(record))
    card = store.export_card()
    routes = Counter(op["route"] for op in operations)
    card["operations"] = operations
    card["metrics"]["route_counts"] = dict(routes)
    card["metrics"]["blocked_rows"] = routes.get("BLOCK_MEMORY_CONTAMINATION", 0)
    card["metrics"]["review_rows"] = routes.get("HOLD_MEMORY_SCHEMA_REVIEW", 0)
    return card


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Typed no-authority knowledge-graph memory store.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    card = build_store_card(read_jsonl(args.manifest))
    text = json.dumps(card, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
