from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from context_packer_v1 import evaluate_memory_items, pack_context


def test_pack_context_prioritizes_required_and_high_value_edges() -> None:
    rows = [
        {"item_id": "low", "text": "general note", "source_type": "doc", "token_len": 8, "retrieval_score": 0.1},
        {"item_id": "sym", "text": "definition of target symbol", "source_type": "symbol", "token_len": 8, "retrieval_score": 0.9, "grounding_score": 1.0, "required": True},
        {"item_id": "test", "text": "failing pytest assertion", "source_type": "test", "token_len": 8, "retrieval_score": 0.8, "grounding_score": 1.0},
    ]
    card = pack_context(rows, token_budget=16, min_required=1)
    assert card["passed"] is True
    selected_ids = [item["item_id"] for item in card["selected_items"]]
    assert "sym" in selected_ids
    assert "test" in selected_ids
    assert "low" not in selected_ids


def test_pack_context_blocks_contaminated_oracle_text() -> None:
    rows = [
        {"item_id": "good", "text": "public source span", "source_type": "source", "token_len": 5, "retrieval_score": 1.0},
        {"item_id": "bad", "text": "oracle target_body answer", "source_type": "source", "token_len": 5, "retrieval_score": 1.0},
    ]
    card = pack_context(rows, token_budget=20)
    assert [item["item_id"] for item in card["selected_items"]] == ["good"]
    assert card["dropped_items"][0]["reason"] == "contamination"


def test_pack_context_deduplicates_before_budgeting() -> None:
    rows = [
        {"item_id": "a", "text": "same source span", "duplicate_group": "g", "token_len": 5, "retrieval_score": 0.9},
        {"item_id": "b", "text": "same source span", "duplicate_group": "g", "token_len": 5, "retrieval_score": 0.8},
    ]
    card = pack_context(rows, token_budget=20)
    assert card["selected_count"] == 1
    assert card["dropped_items"][0]["reason"] == "duplicate"


def test_memory_evaluator_flags_stale_duplicate_and_contaminated_memory() -> None:
    rows = [
        {"item_id": "m1", "text": "old memory", "source_type": "memory", "freshness_score": 0.1, "duplicate_group": "d"},
        {"item_id": "m2", "text": "old memory copy", "source_type": "memory", "freshness_score": 0.9, "duplicate_group": "d"},
        {"item_id": "m3", "text": "expected_answer leaked", "source_type": "memory", "freshness_score": 0.9},
    ]
    card = evaluate_memory_items(rows)
    assert "m1" in card["stale_memory_ids"]
    assert "m3" in card["contaminated_ids"]
    assert card["duplicate_groups"]["d"] == ["m1", "m2"]
