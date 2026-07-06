from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8963_focused_manifest_patch_queue_interpretation import (  # noqa: E402
    AUTHORITY_CLOSED,
    REPAIR_REQUIREMENTS,
    build_card,
    validate_card,
)


def registry(latest: int = 8962) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8963_identifies_combo_shortcut_not_single_shortcut() -> None:
    card = build_card(registry())
    assert card["metrics"]["strongest_single_feature_exact"] < 0.8
    assert card["metrics"]["strongest_combo_feature_exact"] == 1.0
    assert card["metrics"]["combo_exact_1_0_rows"] >= 1
    assert card["metrics"]["manifest_trainable_now"] is False


def test_stage8963_records_counterbalance_repair_requirements() -> None:
    card = build_card(registry())
    assert len(REPAIR_REQUIREMENTS) >= 6
    assert "add_neutral_non_label_evidence_features" in REPAIR_REQUIREMENTS
    assert "rerun_shortcut_baselines_before_trainability" in REPAIR_REQUIREMENTS
    assert card["checks"]["training_blocked_by_shortcut_dominance"] is True


def test_stage8963_validation_keeps_training_and_mining_closed() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_train = build_card(registry())
    bad_train["metrics"]["manifest_trainable_now"] = True
    assert "manifest_trainable_now" in validate_card(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
