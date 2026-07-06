from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8965_registry_spine_reconciliation_after_focused_manifest_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEXT_BRANCH_OPTIONS,
    SPINE_STATUS,
    build_card,
    validate_card,
)


def registry(latest: int = 8964) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8965_reconciles_focused_manifest_as_non_trainable() -> None:
    card = build_card(registry())
    assert card["metrics"]["source_summaries_passed"] == card["metrics"]["source_summaries"]
    assert len(SPINE_STATUS) >= 3
    assert all(row["trainable_now"] is False for row in SPINE_STATUS)
    assert card["metrics"]["focused_manifest_trainable_now"] is False
    assert card["metrics"]["counterbalance_templates_trainable_now"] is False


def test_stage8965_only_allows_no_execution_branches_now() -> None:
    card = build_card(registry())
    allowed = {row["branch"] for row in NEXT_BRANCH_OPTIONS if row["allowed_now"]}
    assert allowed == {"continue_no_execution_recovery", "repo_local_manifest_audit_only"}
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8965_validation_rejects_authority_or_trainability_reopen() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_trainable = build_card(registry())
    bad_trainable["metrics"]["focused_manifest_trainable_now"] = True
    assert "focused_manifest_trainable_now" in validate_card(bad_trainable, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
