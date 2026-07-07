from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9118_metadata_inventory_runner_execution_authorization_review import (  # noqa: E402
    AUTHORITY_CLOSED,
    CURRENT_BLOCKERS,
    REQUIRED_BEFORE_EXECUTION,
    build_card,
    validate_card,
)


def registry(latest: int = 9117) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9118_records_execution_requirements_and_blockers() -> None:
    card = build_card(registry())

    assert card["checks"]["source_stage9117_passed"] is True
    assert card["checks"]["source_stage9117_runner_not_executed"] is True
    assert set(REQUIRED_BEFORE_EXECUTION).issubset(card["required_before_execution"])
    assert set(CURRENT_BLOCKERS).issubset(card["current_blockers"])
    assert "explicit_user_inventory_execution_request_missing" in card["current_blockers"]
    assert "final_pre_execution_audit_missing" in card["current_blockers"]


def test_stage9118_keeps_inventory_execution_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]

    assert metrics["inventory_execution_authorized_now"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert metrics["runner_executed_now"] is False
    assert metrics["arxiv_access_performed"] is False
    assert metrics["dataset_file_names_read_now"] is False
    assert metrics["repository_root_names_read_now"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9118_validation_rejects_missing_requirements_open_paths_or_bad_frontier() -> None:
    card = build_card(registry())
    assert validate_card(card, registry()) == []

    missing_requirement = build_card(registry())
    missing_requirement["required_before_execution"].remove("final_pre_execution_audit_passed")
    assert "missing_required_before_execution:final_pre_execution_audit_passed" in validate_card(missing_requirement, registry())

    missing_blocker = build_card(registry())
    missing_blocker["current_blockers"].remove("single_run_inventory_ticket_missing")
    assert "missing_current_blocker:single_run_inventory_ticket_missing" in validate_card(missing_blocker, registry())

    authorized = build_card(registry())
    authorized["metrics"]["inventory_execution_authorized_next"] = True
    assert "inventory_execution_authorized_next" in validate_card(authorized, registry())

    runner = build_card(registry())
    runner["metrics"]["runner_executed_now"] = True
    assert "runner_executed_now" in validate_card(runner, registry())

    arxiv = build_card(registry())
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_card(arxiv, registry())

    authority = build_card(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_card(card, registry(latest=9999))
