from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

AUTHORITY_CLOSED = {
    "model_execution": False,
    "training": False,
    "runtime": False,
    "source_body_emission": False,
}

FORBIDDEN_ID_TERMS = {
    "symbol_binding",
    "edit_localization",
    "patch_operator",
    "verifier_repair",
    "bounded_decoder",
    "expected_answer",
    "target_body",
    "oracle",
}


def stable_hash(text: str) -> int:
    return int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16)


def hashed_vector(text: str, dim: int) -> list[float]:
    if dim <= 0:
        raise ValueError("dim must be positive")
    values = [0.0] * dim
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    for index, byte in enumerate(digest):
        slot = (byte + index * 17) % dim
        sign = 1.0 if byte % 2 == 0 else -1.0
        values[slot] += sign * ((byte % 11) + 1) / 11.0
    return values


def add_vectors(left: list[float], right: Iterable[float], *, scale: float = 1.0) -> None:
    for index, value in enumerate(right):
        if index < len(left):
            left[index] += scale * float(value)


def normalize(values: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in values))
    if norm <= 1e-12:
        return values
    return [float(value / norm) for value in values]


def _node_id(node: Mapping[str, Any]) -> str:
    return str(node.get("node_id") or node.get("id") or "")


def _node_kind(node: Mapping[str, Any]) -> str:
    return str(node.get("node_type") or node.get("kind") or node.get("type") or "unknown")


def _edge_src(edge: Mapping[str, Any]) -> str:
    return str(edge.get("src") or edge.get("source") or "")


def _edge_dst(edge: Mapping[str, Any]) -> str:
    return str(edge.get("dst") or edge.get("target") or "")


def _edge_relation(edge: Mapping[str, Any]) -> str:
    return str(edge.get("edge_type") or edge.get("relation") or "unknown")


def _feature_terms(node: Mapping[str, Any]) -> list[str]:
    terms = [_node_kind(node)]
    features = node.get("features", {})
    if isinstance(features, Mapping):
        for key, value in sorted(features.items()):
            if isinstance(value, (str, int, float, bool)):
                terms.append(f"{key}={value}")
            elif isinstance(value, list):
                terms.append(f"{key}:len={len(value)}")
    return terms


def audit_graph_packet(graph: Mapping[str, Any]) -> dict[str, Any]:
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    ids = {_node_id(node) for node in nodes if _node_id(node)}
    endpoint_failures = []
    for edge in edges:
        src = _edge_src(edge)
        dst = _edge_dst(edge)
        if src not in ids or dst not in ids:
            endpoint_failures.append({"src": src, "dst": dst, "relation": _edge_relation(edge)})
    label_leak_ids = []
    for value in list(ids) + [str(graph.get("graph_id", ""))]:
        lower = value.lower()
        if any(term in lower for term in FORBIDDEN_ID_TERMS):
            label_leak_ids.append(value)
    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "endpoint_failures": endpoint_failures,
        "endpoint_failure_count": len(endpoint_failures),
        "label_leak_ids": label_leak_ids,
        "label_leak_count": len(label_leak_ids),
        "passed": len(nodes) > 0 and len(endpoint_failures) == 0 and len(label_leak_ids) == 0,
    }


def encode_repo_graph(graph: Mapping[str, Any], *, dim: int = 32, rounds: int = 2) -> dict[str, Any]:
    if rounds < 0:
        raise ValueError("rounds must be non-negative")
    audit = audit_graph_packet(graph)
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    node_by_id = {_node_id(node): node for node in nodes if _node_id(node)}
    incoming: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    outgoing: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    relation_counts: Counter[str] = Counter()
    for edge in edges:
        src = _edge_src(edge)
        dst = _edge_dst(edge)
        relation = _edge_relation(edge)
        relation_counts[relation] += 1
        outgoing[src].append(edge)
        incoming[dst].append(edge)
    states: dict[str, list[float]] = {}
    for node_id, node in node_by_id.items():
        vec = [0.0] * dim
        for term in _feature_terms(node):
            add_vectors(vec, hashed_vector(f"node:{term}", dim), scale=1.0)
        add_vectors(vec, hashed_vector(f"in_degree:{len(incoming[node_id])}", dim), scale=0.25)
        add_vectors(vec, hashed_vector(f"out_degree:{len(outgoing[node_id])}", dim), scale=0.25)
        states[node_id] = normalize(vec)
    for _ in range(rounds):
        next_states = {node_id: [0.6 * value for value in state] for node_id, state in states.items()}
        for edge in edges:
            src = _edge_src(edge)
            dst = _edge_dst(edge)
            relation = _edge_relation(edge)
            if src not in states or dst not in next_states:
                continue
            message = list(states[src])
            add_vectors(message, hashed_vector(f"relation:{relation}", dim), scale=0.15)
            add_vectors(next_states[dst], message, scale=0.4 / max(1, len(incoming[dst])))
        states = {node_id: normalize(vec) for node_id, vec in next_states.items()}
    graph_vec = [0.0] * dim
    for vec in states.values():
        add_vectors(graph_vec, vec, scale=1.0 / max(1, len(states)))
    kind_counts = Counter(_node_kind(node) for node in nodes)
    node_cards = []
    for node_id, vec in sorted(states.items()):
        node_cards.append({
            "node_id": node_id,
            "node_type": _node_kind(node_by_id[node_id]),
            "in_degree": len(incoming[node_id]),
            "out_degree": len(outgoing[node_id]),
            "embedding_hash": hashlib.sha256(json.dumps([round(v, 6) for v in vec], sort_keys=True).encode("utf-8")).hexdigest()[:16],
            "embedding": vec,
        })
    return {
        "passed": audit["passed"],
        "audit": audit,
        "dim": dim,
        "rounds": rounds,
        "node_embeddings": node_cards,
        "graph_embedding": normalize(graph_vec),
        "graph_embedding_hash": hashlib.sha256(json.dumps([round(v, 6) for v in normalize(graph_vec)], sort_keys=True).encode("utf-8")).hexdigest()[:16],
        "node_type_counts": dict(sorted(kind_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "authority": AUTHORITY_CLOSED,
    }


def _sample_graph() -> dict[str, Any]:
    return {
        "graph_id": "graph_opaque_sample",
        "nodes": [
            {"node_id": "n_repo", "node_type": "repo", "features": {"language": "python"}},
            {"node_id": "n_file", "node_type": "file", "features": {"suffix": ".py"}},
            {"node_id": "n_symbol", "node_type": "symbol", "features": {"kind": "function"}},
            {"node_id": "n_test", "node_type": "test", "features": {"kind": "unit"}},
        ],
        "edges": [
            {"src": "n_repo", "dst": "n_file", "edge_type": "contains"},
            {"src": "n_file", "dst": "n_symbol", "edge_type": "defines"},
            {"src": "n_test", "dst": "n_symbol", "edge_type": "test_covers"},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Encode audited repo-state graph packets with deterministic message passing; no model execution.")
    parser.add_argument("--input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dim", type=int, default=32)
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    graph = json.loads(args.input.read_text(encoding="utf-8")) if args.input else _sample_graph()
    card = encode_repo_graph(graph, dim=args.dim, rounds=args.rounds)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
