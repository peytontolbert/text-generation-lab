from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from query_expansion_rewriter import expand_query, query_expansion_card


def test_expands_from_visible_symbol_error_and_api_hints() -> None:
    record = expand_query({
        "row_id": "r1",
        "intent": "fix auth failure",
        "symbol": "validate_user",
        "error": "AssertionError expected 403 got 200",
        "api": "FastAPI Depends",
        "language": "python",
    })
    assert record["query_expansion_route"] == "PASS_QUERY_EXPANSION"
    assert "validate_user definition references" in record["query_variants"]
    assert any("AssertionError" in variant for variant in record["query_variants"])
    assert record["query_source_bits"]["symbol"] is True
    assert record["authority"]["training_authorized"] is False


def test_blocks_visible_target_fields() -> None:
    record = expand_query({"row_id": "leak", "intent": "fix", "target_label": "CORRECT_PRIOR"})
    assert record["query_expansion_route"] == "BLOCK_QUERY_EXPANSION_LEAK"
    assert record["query_variants"] == []
    assert record["leak_or_target_rows"] == 1


def test_holds_when_no_visible_hints() -> None:
    record = expand_query({"row_id": "empty"})
    assert record["query_expansion_route"] == "HOLD_QUERY_EXPANSION_NO_HINTS"
    assert record["query_variants"] == []


def test_query_expansion_card_counts_source_bits_and_routes() -> None:
    card = query_expansion_card([
        {"row_id": "ok", "symbol": "foo", "path": "src/foo.py"},
        {"row_id": "hold"},
        {"row_id": "block", "clean_state": {"patch_operator": "ADD_IMPORT"}},
    ])
    assert card["metrics"]["pass_rows"] == 1
    assert card["metrics"]["hold_rows"] == 1
    assert card["metrics"]["blocked_rows"] == 1
    assert card["metrics"]["leak_or_target_rows"] == 1
    assert card["metrics"]["expansion_source_bits"]["symbol"] == 1
    assert card["metrics"]["authority_rows"] == 0
