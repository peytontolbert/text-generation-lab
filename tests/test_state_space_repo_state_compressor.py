from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from state_space_repo_state_compressor import selective_scan_compress


def test_compressor_emits_fixed_dim_state_and_hints() -> None:
    rows = [
        {"event_id": "s1", "event_type": "source", "text": "def login(): return check_user()", "importance": 0.8, "retrieval_score": 0.9, "grounding_score": 1.0, "token_len": 8},
        {"event_id": "t1", "event_type": "test", "text": "assert login() is True", "importance": 0.7, "retrieval_score": 0.8, "grounding_score": 1.0, "token_len": 7},
    ]
    card = selective_scan_compress(rows, state_dim=32, token_budget=64)
    assert card["passed"] is True
    assert len(card["state_vector"]) == 32
    assert 0.99 <= card["state_norm"] <= 1.01
    assert [hint["event_id"] for hint in card["retrieval_hints"]] == ["s1", "t1"]


def test_compressor_blocks_oracle_contamination() -> None:
    rows = [
        {"event_id": "good", "event_type": "source", "text": "public span", "importance": 1.0},
        {"event_id": "bad", "event_type": "source", "text": "oracle target_body expected_answer", "importance": 1.0},
    ]
    card = selective_scan_compress(rows, state_dim=32)
    assert card["events_accepted"] == 1
    assert card["dropped_events"][0]["reason"] == "contamination"


def test_compressor_is_deterministic_for_same_stream() -> None:
    rows = [
        {"event_id": "e1", "event_type": "error", "text": "ValueError in parser", "importance": 0.9, "recency": 0.5},
        {"event_id": "d1", "event_type": "dependency", "text": "import yaml", "importance": 0.4},
    ]
    a = selective_scan_compress(rows, state_dim=40)
    b = selective_scan_compress(rows, state_dim=40)
    assert a["compressed_repo_state"]["state_vector_hash"] == b["compressed_repo_state"]["state_vector_hash"]
    assert a["state_vector"] == b["state_vector"]


def test_low_value_events_can_be_budget_dropped() -> None:
    rows = [
        {"event_id": "important", "event_type": "symbol", "text": "critical symbol", "importance": 1.0, "token_len": 5},
        {"event_id": "low", "event_type": "doc", "text": "long low value doc", "importance": 0.0, "token_len": 100},
    ]
    card = selective_scan_compress(rows, state_dim=32, token_budget=16)
    assert [hint["event_id"] for hint in card["retrieval_hints"]] == ["important"]
    assert any(drop["event_id"] == "low" and drop["reason"] == "budget" for drop in card["dropped_events"])
