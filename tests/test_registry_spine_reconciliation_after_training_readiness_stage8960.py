from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8960_registry_spine_reconciliation_after_training_readiness_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    CURRENT_BLOCKED_AUTHORITY,
    GRAPH_ATTACHMENTS,
    build_card,
    validate_card,
)


def registry(latest: int = 8959) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8960_attaches_recent_recovery_chain_to_spine() -> None:
    card = build_card(registry())
    assert card["metrics"]["source_summaries_passed"] == card["metrics"]["source_summaries"]
    assert len(GRAPH_ATTACHMENTS) >= 5
    node_ids = {row["node_id"] for row in GRAPH_ATTACHMENTS}
    assert "objective:bounded_decoder_ce" in node_ids
    assert "support_module:no_mining_curriculum_compiler" in node_ids
    assert "training:readiness_blocker_matrix" in node_ids


def test_stage8960_records_blocked_authority_and_training_not_ready() -> None:
    card = build_card(registry())
    for authority in ["model_execution", "decoder_ce_training", "data_mining", "arxiv_compiler_io"]:
        assert authority in CURRENT_BLOCKED_AUTHORITY
    assert card["metrics"]["training_ready"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage8960_validation_rejects_authority_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad, registry())
    bad_train = build_card(registry())
    bad_train["metrics"]["training_ready"] = True
    assert "training_ready" in validate_card(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
