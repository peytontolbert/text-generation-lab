from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9073_central_graph_gap_walk_after_trainer_docs import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_EXISTING_CONTROL_NODES,
    STAGE9072_EXPECTED_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9072) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9073_confirms_existing_trainer_controls() -> None:
    card = build_card(registry())
    assert card["checks"]["existing_trainer_controls_attached"] is True
    assert card["metrics"]["present_existing_control_nodes"] == len(REQUIRED_EXISTING_CONTROL_NODES)
    assert card["metrics"]["missing_existing_control_nodes"] == 0


def test_stage9073_identifies_stage9072_graph_attachment_gap() -> None:
    card = build_card(registry())
    assert card["checks"]["stage9072_attachment_gap_identified"] is True
    assert card["metrics"]["stage9072_missing_nodes"] == len(STAGE9072_EXPECTED_NODES)
    assert card["metrics"]["stage9072_missing_edges"] > 0
    assert card["unresolved_gaps"][0]["gap_id"] == "stage9072_graph_attachment_missing"


def test_stage9073_validation_rejects_execution_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []
    bad = build_card(registry())
    bad["metrics"]["model_forward_attempted"] = True
    assert "model_forward_attempted" in validate_card(bad, registry())
    bad_authority = build_card(registry())
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
