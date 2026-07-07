from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9121_metadata_inventory_final_pre_execution_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    FINAL_REQUIREMENTS,
    build_audit,
    validate_audit,
)


def registry(latest: int = 9120) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9121_review_audit_records_sources_and_blocker() -> None:
    audit = build_audit(registry())

    assert audit["checks"]["source_stage9117_passed"] is True
    assert audit["checks"]["source_stage9118_passed"] is True
    assert audit["checks"]["source_stage9120_passed"] is True
    assert audit["checks"]["stage9117_runner_not_executed"] is True
    assert audit["checks"]["stage9118_execution_not_authorized"] is True
    assert audit["checks"]["stage9120_ticket_rejected_negative_cases"] is True
    assert set(FINAL_REQUIREMENTS).issubset(audit["final_requirements"])
    assert "explicit_user_inventory_execution_request_missing" in audit["current_blockers"]


def test_stage9121_keeps_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["explicit_user_inventory_execution_request_present"] is False
    assert metrics["final_pre_execution_audit_passed_for_execution"] is False
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
    assert not any(audit["authority"].values())


def test_stage9121_validation_rejects_open_execution_or_bad_frontier() -> None:
    audit = build_audit(registry())
    assert validate_audit(audit, registry()) == []

    authorized = build_audit(registry())
    authorized["metrics"]["inventory_execution_authorized_next"] = True
    assert "inventory_execution_authorized_next" in validate_audit(authorized, registry())

    request_present = build_audit(registry())
    request_present["metrics"]["explicit_user_inventory_execution_request_present"] = True
    assert "explicit_user_inventory_execution_request_present" in validate_audit(request_present, registry())

    final_pass = build_audit(registry())
    final_pass["metrics"]["final_pre_execution_audit_passed_for_execution"] = True
    assert "final_pre_execution_audit_passed_for_execution" in validate_audit(final_pass, registry())

    runner = build_audit(registry())
    runner["metrics"]["runner_executed_now"] = True
    assert "runner_executed_now" in validate_audit(runner, registry())

    missing_blocker = build_audit(registry())
    missing_blocker["current_blockers"] = []
    assert "missing_current_blocker:explicit_user_inventory_execution_request_missing" in validate_audit(missing_blocker, registry())

    authority = build_audit(registry())
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_audit(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_audit(audit, registry(latest=9999))
