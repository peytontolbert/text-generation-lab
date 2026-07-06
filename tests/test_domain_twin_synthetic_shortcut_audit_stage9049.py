from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage9049_domain_twin_synthetic_shortcut_audit import build_card, validate_card  # noqa: E402


def test_stage9049_synthetic_shortcut_audit_is_nontraining_only() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    assert validate_card(card) == []
    assert card["metrics"]["synthetic_rows_trainable"] is False
    assert card["metrics"]["training_quality_claim_allowed"] is False
    assert card["checks"]["all_rows_route_needs_human_review"] is True
    assert card["checks"]["all_loss_masks_closed"] is True


def test_stage9049_validation_rejects_training_claims() -> None:
    card = build_card({"metrics": {"authority_counts": {}}})
    card["metrics"]["synthetic_rows_trainable"] = True
    card["authority"]["model_execution_authorized_next"] = True
    failures = validate_card(card)
    assert "synthetic_rows_trainable" in failures
    assert "authority_open" in failures
