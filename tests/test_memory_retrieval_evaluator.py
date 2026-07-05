from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from memory_retrieval_evaluator import evaluate_memories, evaluate_memory


def test_passes_relevant_fresh_memory_with_lineage() -> None:
    record = evaluate_memory({"memory_id": "m1", "relevance_score": 0.9, "staleness_days": 3, "source_id": "src"})
    assert record["memory_route"] == "PASS_MEMORY_RETRIEVAL"


def test_holds_low_relevance() -> None:
    record = evaluate_memory({"memory_id": "m2", "relevance_score": 0.2, "source_id": "src"})
    assert record["memory_route"] == "HOLD_MEMORY_REVIEW"
    assert "low_relevance" in record["reasons"]


def test_holds_stale_duplicate() -> None:
    record = evaluate_memory({"memory_id": "m3", "relevance_score": 0.8, "staleness_days": 120, "duplicate_of": "m1", "source_id": "src"})
    assert record["memory_route"] == "HOLD_MEMORY_REVIEW"
    assert "stale_memory" in record["reasons"]
    assert "duplicate_memory" in record["reasons"]


def test_blocks_contaminated_memory() -> None:
    record = evaluate_memory({"memory_id": "m4", "relevance_score": 0.9, "source_id": "src", "locked_eval_source": True})
    assert record["memory_route"] == "BLOCK_MEMORY_CONTAMINATION"
    assert record["blocked"] is True


def test_holds_missing_lineage() -> None:
    record = evaluate_memory({"memory_id": "m5", "relevance_score": 0.9})
    assert record["memory_route"] == "HOLD_MEMORY_REVIEW"
    assert "missing_memory_lineage" in record["reasons"]


def test_manifest_counts_routes() -> None:
    card = evaluate_memories([
        {"memory_id": "pass", "relevance_score": 0.9, "source_id": "src"},
        {"memory_id": "review", "relevance_score": 0.1, "source_id": "src"},
        {"memory_id": "block", "relevance_score": 0.9, "source_id": "src", "hidden_eval_source": True},
    ])
    assert card["metrics"]["pass_memories"] == 1
    assert card["metrics"]["review_memories"] == 1
    assert card["metrics"]["blocked_memories"] == 1
