from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from feature_normalizer import normalize_features
from source_lineage_guard import evaluate_row_source_lineage, locked_source_ids, train_eligible_source_ids


def test_feature_normalizer_extracts_nested_and_array_aliases() -> None:
    row = {
        "row_id": "r",
        "graph_input": {
            "query_kind": "callsite",
            "nodes": [
                {"node_type": "file", "features": {"call_count_bucket": "low"}},
                {"node_type": "function", "features": {"call_count_bucket": "high"}},
            ],
        },
    }
    aliases = {
        "query_kind": ["graph_input.query_kind"],
        "call_count_bucket": ["graph_input.nodes[].features.call_count_bucket"],
    }
    normalized = normalize_features(row, aliases)
    assert normalized["query_kind"] == "callsite"
    assert normalized["call_count_bucket"] == ["low", "high"]


def test_source_guard_blocks_locked_source() -> None:
    registry = {
        "src_locked": {"source_id": "src_locked", "locked_eval": True, "train_eligible": False},
    }
    row = {"row_id": "r", "source_lineage": {"graph_nodes_source_id": "src_locked"}}
    result = evaluate_row_source_lineage(row, registry)
    assert result["train_eligible_lineage"] is False
    assert result["blocked_training_reason"] == "locked_eval_source"
    assert locked_source_ids(registry) == {"src_locked"}


def test_source_guard_blocks_unknown_source() -> None:
    result = evaluate_row_source_lineage({"source_lineage": {"source_id": "missing"}}, {})
    assert result["train_eligible_lineage"] is False
    assert result["blocked_training_reason"] == "unknown_source_id"


def test_source_guard_accepts_train_eligible_source() -> None:
    registry = {
        "src_ok": {"source_id": "src_ok", "locked_eval": False, "hidden_final": False, "train_eligible": True},
    }
    row = {"source_lineage": {"graph_nodes_source_id": "src_ok", "graph_spans_source_id": "src_ok"}}
    result = evaluate_row_source_lineage(row, registry)
    assert result["train_eligible_lineage"] is True
    assert train_eligible_source_ids(registry) == {"src_ok"}
