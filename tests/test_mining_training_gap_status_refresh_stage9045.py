from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9045_mining_training_gap_status_refresh import (  # noqa: E402
    BLOCKED_NOW,
    REMAINING_BEFORE_BROAD_MINING,
    build_card,
    validate_card,
)


def test_stage9045_refresh_keeps_broad_mining_and_training_closed() -> None:
    card = build_card({"metrics": {"latest_stage": 9044, "authority_counts": {}}})
    assert validate_card(card) == []
    assert "broad_arxiv_mining" in BLOCKED_NOW
    assert "train_100m_model" in BLOCKED_NOW
    assert "active_source_ticket_for_arxiv_or_repository_library_reads" in REMAINING_BEFORE_BROAD_MINING
    assert card["metrics"]["broad_mining_authorized"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9045_validation_rejects_open_source_or_training() -> None:
    card = build_card({"metrics": {"latest_stage": 9044, "authority_counts": {}}})
    card["metrics"]["repository_source_body_read_authorized_now"] = True
    card["authority"]["source_emission_authorized"] = True
    failures = validate_card(card)
    assert "repository_source_body_read_authorized_now" in failures
    assert "authority_open" in failures
