from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))

from long_context_common import extract_terms, should_keep_term  # noqa: E402
from scripts.build_stage9050_long_context_term_noise_filter_audit import build_card, validate_card  # noqa: E402


def test_term_noise_filter_drops_structured_noise_and_keeps_semantic_terms() -> None:
    text = "timestamp payload response_item retrieval verifier counterfactual token_count source_id regression"
    terms = extract_terms(text, max_terms=20, source_type="dataset", modality="structured_text")
    assert "timestamp" not in terms
    assert "payload" not in terms
    assert "token_count" not in terms
    assert "retrieval" in terms
    assert "verifier" in terms
    assert should_keep_term("regression") is True


def test_stage9050_audit_keeps_indexing_and_training_closed() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert card["metrics"]["corpus_index_executed_now"] is False
    assert card["metrics"]["arxiv_scan_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False
