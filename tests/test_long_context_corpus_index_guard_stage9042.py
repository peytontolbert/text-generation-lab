from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9042_long_context_corpus_index_guard_audit import (  # noqa: E402
    FORBIDDEN_DEFAULT_AUTHORITY,
    build_card,
    validate_card,
)


def test_stage9042_guard_card_keeps_production_corpus_index_closed() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert card["checks"]["all_required_guards_present"] is True
    assert card["checks"]["spec_marks_arxiv_as_future_gated"] is True
    assert card["checks"]["test_covers_default_refusal"] is True
    for key in FORBIDDEN_DEFAULT_AUTHORITY:
        assert card["metrics"][key] is False
    assert card["metrics"]["production_corpus_index_authorized_now"] is False


def test_stage9042_validation_rejects_open_authority() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    card["metrics"]["arxiv_write_authorized"] = True
    card["authority"]["runtime_authorized"] = True
    failures = validate_card(card)
    assert "arxiv_write_authorized" in failures
    assert "authority_open" in failures
