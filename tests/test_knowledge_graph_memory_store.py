from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from knowledge_graph_memory_store import KnowledgeGraphMemoryStore, build_store_card


def test_upserts_node_with_stable_memory_key() -> None:
    store = KnowledgeGraphMemoryStore()
    result = store.upsert_node({"node_type": "skill", "memory_key": "repair unsafe import", "tags": ["repair", "import"]})
    assert result["route"] == "PASS_MEMORY_NODE_UPSERT"
    assert result["node"]["promotion_authority"] is False
    again = store.upsert_node({"node_type": "skill", "memory_key": "repair unsafe import", "tags": ["unsafe"]})
    assert again["node_id"] == result["node_id"]
    assert again["node"]["tags"] == ["import", "repair", "unsafe"]


def test_blocks_locked_eval_or_contaminated_memory() -> None:
    store = KnowledgeGraphMemoryStore()
    result = store.upsert_node({"node_type": "source_fact", "memory_key": "hidden answer", "locked_eval_source": True})
    assert result["route"] == "BLOCK_MEMORY_CONTAMINATION"
    assert "locked_eval_source" in result["reasons"]
    assert store.export_card()["metrics"]["node_count"] == 0


def test_adds_edges_and_retrieval_path() -> None:
    store = KnowledgeGraphMemoryStore()
    a = store.upsert_node({"node_type": "repo_entity", "memory_key": "auth.py", "label": "auth module"})["node_id"]
    b = store.upsert_node({"node_type": "eval_trace", "memory_key": "test_auth_failure", "label": "auth failure"})["node_id"]
    edge = store.upsert_edge({"src": a, "dst": b, "edge_type": "verified_by"})
    assert edge["route"] == "PASS_MEMORY_EDGE_UPSERT"
    path = store.retrieval_path(a, b)
    assert path["route"] == "PASS_MEMORY_PATH"
    assert path["path"][0]["node_id"] == a
    assert path["path"][-1]["node_id"] == b


def test_query_by_tag_and_text() -> None:
    store = KnowledgeGraphMemoryStore()
    store.upsert_node({"node_type": "tool_outcome", "memory_key": "pytest auth pass", "label": "pytest auth pass", "tags": ["pytest"]})
    result = store.query(text="auth", tags=["pytest"])
    assert result["route"] == "PASS_MEMORY_RETRIEVAL"
    assert result["result_count"] == 1


def test_build_store_card_counts_block_and_review() -> None:
    card = build_store_card([
        {"node_type": "skill", "memory_key": "ok"},
        {"node_type": "bad_type", "memory_key": "review"},
        {"node_type": "source_fact", "memory_key": "blocked", "contamination_risk": True},
    ])
    assert card["metrics"]["node_count"] == 1
    assert card["metrics"]["review_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
    assert card["metrics"]["authority_rows"] == 0
