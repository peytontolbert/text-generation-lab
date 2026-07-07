from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9144_real_route_card_input_ticket_instance_blocker_audit import (  # noqa: E402
    FORBIDDEN_UNTIL_UNBLOCKED,
    REQUIRED_BLOCKERS,
    build_blocker,
    run_negative_cases,
    validate_blocker,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9143) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9144_blocker_passes_and_records_missing_inputs() -> None:
    card = build_blocker(registry())

    assert validate_blocker(card, registry()) == []
    assert all(card["checks"].values())
    assert set(REQUIRED_BLOCKERS).issubset(set(card["required_blockers"]))
    assert "explicit_user_approval_for_ticket_instance_missing" in card["required_blockers"]
    assert "objective_rows_path_missing" in card["required_blockers"]
    assert "judge_rows_path_missing" in card["required_blockers"]
    assert "junk_ranker_rows_path_missing" in card["required_blockers"]
    assert card["metrics"]["ticket_instance_blocked"] is True
    assert not any(card["authority"].values())


def test_stage9144_records_all_forbidden_actions_until_unblocked() -> None:
    card = build_blocker(registry())

    assert set(FORBIDDEN_UNTIL_UNBLOCKED).issubset(set(card["forbidden_until_unblocked"]))
    for key in FORBIDDEN_UNTIL_UNBLOCKED:
        assert card["metrics"][key] is False
    assert card["metrics"]["real_judge_rows_used"] == 0
    assert card["metrics"]["real_ranker_rows_used"] == 0
    assert card["metrics"]["real_route_cards_materialized"] == 0


def test_stage9144_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_blocker:explicit_user_approval_for_ticket_instance_missing" in negatives["missing_explicit_approval_blocker"]["failures"]
    assert "missing_blocker:objective_rows_path_missing" in negatives["missing_objective_path_blocker"]["failures"]
    assert "ticket_instance_not_blocked" in negatives["ticket_instance_unblocked"]["failures"]
    assert "ticket_instance_materialized" in negatives["ticket_instance_materialized"]["failures"]
    assert "real_input_authorized_now" in negatives["real_input_authorized_now"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized_now"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized_flag"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9144_bad_registry_frontier_fails() -> None:
    card = build_blocker(registry())

    assert "unexpected_registry_frontier:9999" in validate_blocker(card, registry(latest=9999))
