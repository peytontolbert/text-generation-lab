from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9157_repo_local_inventory_final_authorization_design_audit import (  # noqa: E402
    AUTHORIZATION_BOUNDARIES,
    NEGATIVE_CASES,
    REQUIRED_BLOCKER_EVIDENCE,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9157_audit_passes_with_stage9156_frontier() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9156_passed"] is True
    assert audit["checks"]["source_design_valid"] is True
    assert audit["checks"]["execution_not_authorized_now"] is True
    assert audit["checks"]["execution_not_authorized_next"] is True
    assert audit["checks"]["registry_frontier_stage9156"] is True


def test_stage9157_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9156_not_passed" in negatives["source_stage9156_missing"]["failures"]
    assert "missing_required_before_execution:explicit_user_inventory_execution_request" in negatives["missing_required_before_execution"]["failures"]
    assert "missing_current_blocker:explicit_user_inventory_execution_request_missing" in negatives["missing_current_blocker"]["failures"]
    assert "missing_forbidden_during_execution:access_arxiv" in negatives["missing_forbidden_during_execution"]["failures"]
    assert "missing_blocker_evidence:registry_has_no_open_authority_counts" in negatives["missing_blocker_evidence"]["failures"]
    assert "missing_authorization_boundary:must_not_authorize_route_card_materialization" in negatives["missing_authorization_boundary"]["failures"]
    assert "inventory_execution_authorized_now" in negatives["execution_authorized_now"]["failures"]
    assert "inventory_execution_authorized_next" in negatives["execution_authorized_next"]["failures"]
    assert "metadata_path_inventory_materialized_now" in negatives["inventory_materialized_now"]["failures"]
    assert "file_content_read" in negatives["file_content_read"]["failures"]
    assert "json_parsed" in negatives["json_parsed"]["failures"]
    assert "jsonl_rows_counted" in negatives["jsonl_rows_counted"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "arxiv_accessed" in negatives["arxiv_accessed"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9157_rejects_bad_registry_frontier() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9156" in audit["failures"]


def test_stage9157_keeps_inventory_route_and_training_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]
    card = audit["audit_card"]

    assert set(REQUIRED_BLOCKER_EVIDENCE).issubset(set(card["required_blocker_evidence"]))
    assert set(AUTHORIZATION_BOUNDARIES).issubset(set(card["authorization_boundaries"]))
    assert metrics["audit_only"] is True
    assert metrics["inventory_execution_authorized_now"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert metrics["inventory_runner_executed_now"] is False
    assert metrics["metadata_path_inventory_materialized_now"] is False
    assert metrics["file_content_read"] is False
    assert metrics["json_parsed"] is False
    assert metrics["jsonl_rows_counted"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert not any(audit["authority"].values())
