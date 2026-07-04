from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from repo_graph_encoder import audit_graph_packet, encode_repo_graph


def sample_graph() -> dict:
    return {
        "graph_id": "graph_opaque",
        "nodes": [
            {"node_id": "n_repo", "node_type": "repo", "features": {"language": "python"}},
            {"node_id": "n_file", "node_type": "file", "features": {"suffix": ".py"}},
            {"node_id": "n_symbol", "node_type": "symbol", "features": {"kind": "function"}},
        ],
        "edges": [
            {"src": "n_repo", "dst": "n_file", "edge_type": "contains"},
            {"src": "n_file", "dst": "n_symbol", "edge_type": "defines"},
        ],
    }


def test_audit_graph_packet_passes_clean_opaque_graph() -> None:
    audit = audit_graph_packet(sample_graph())
    assert audit["passed"] is True
    assert audit["endpoint_failure_count"] == 0
    assert audit["label_leak_count"] == 0


def test_audit_graph_packet_fails_unresolved_endpoint() -> None:
    graph = sample_graph()
    graph["edges"].append({"src": "n_symbol", "dst": "missing", "edge_type": "calls"})
    audit = audit_graph_packet(graph)
    assert audit["passed"] is False
    assert audit["endpoint_failure_count"] == 1


def test_audit_graph_packet_fails_label_coded_ids() -> None:
    graph = sample_graph()
    graph["nodes"][0]["node_id"] = "node_symbol_binding_leak"
    audit = audit_graph_packet(graph)
    assert audit["passed"] is False
    assert audit["label_leak_count"] == 1


def test_encode_repo_graph_is_deterministic_and_closed_authority() -> None:
    first = encode_repo_graph(sample_graph(), dim=16, rounds=2)
    second = encode_repo_graph(sample_graph(), dim=16, rounds=2)
    assert first["passed"] is True
    assert first["graph_embedding_hash"] == second["graph_embedding_hash"]
    assert len(first["graph_embedding"]) == 16
    assert first["authority"]["training"] is False


def test_message_passing_changes_when_relation_changes() -> None:
    graph = sample_graph()
    base = encode_repo_graph(graph, dim=16, rounds=2)
    changed = sample_graph()
    changed["edges"][1]["edge_type"] = "calls"
    other = encode_repo_graph(changed, dim=16, rounds=2)
    assert base["graph_embedding_hash"] != other["graph_embedding_hash"]
