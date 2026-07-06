from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9044_semantic_intent_surface_bridge import (  # noqa: E402
    SEMANTIC_SURFACES,
    USER_INTENT_FIELDS,
    build_card,
    validate_card,
)


def test_stage9044_records_semantic_surfaces_and_user_intent_fields() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert "maintainer_answer" in SEMANTIC_SURFACES
    assert "bounded_patch_hunk" in SEMANTIC_SURFACES
    assert "intent_type" in USER_INTENT_FIELDS
    assert "blocked_imports" in USER_INTENT_FIELDS
    assert card["metrics"]["semantic_surface_rows_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9044_validation_rejects_open_decoder_or_training() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    card["metrics"]["decoder_ce_authorized"] = True
    card["authority"]["decoder_ce_training_authorized_next"] = True
    failures = validate_card(card)
    assert "decoder_ce_authorized" in failures
    assert "authority_open" in failures
