from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9146_route_card_input_candidate_locator_design_audit import (  # noqa: E402
    NEGATIVE_CASES,
    build_audit,
    run_negative_cases,
)
from scripts.diagnostic_ticket_contract import AUTHORITY_CLOSED  # noqa: E402


def registry(latest: int = 9145) -> dict:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9146_audit_passes_base_locator_design() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["base_failures"] == []
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["allowed_roots_complete"] is True
    assert audit["checks"]["forbidden_roots_complete"] is True
    assert audit["checks"]["candidate_types_complete"] is True
    assert audit["checks"]["locator_rules_complete"] is True
    assert audit["checks"]["locator_not_executed"] is True
    assert audit["checks"]["path_inventory_not_materialized"] is True
    assert audit["checks"]["file_content_not_read"] is True
    assert audit["checks"]["arxiv_not_accessed"] is True
    assert audit["checks"]["authority_closed"] is True


def test_stage9146_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_allowed_search_root:runs/local/artifacts" in negatives["missing_artifact_root"]["failures"]
    assert "missing_allowed_search_root:runs/summaries" in negatives["missing_summary_root"]["failures"]
    assert "missing_forbidden_search_root:/arxiv" in negatives["missing_arxiv_forbidden_root"]["failures"]
    assert "missing_locator_rule:no_file_content_reads" in negatives["missing_no_file_content_rule"]["failures"]
    assert "missing_locator_rule:no_arxiv_reads" in negatives["missing_no_arxiv_rule"]["failures"]
    assert "missing_candidate_type:objective_rows_jsonl" in negatives["missing_objective_candidate_type"]["failures"]
    assert "candidate_locator_executed" in negatives["locator_executed"]["failures"]
    assert "path_inventory_materialized" in negatives["path_inventory_materialized"]["failures"]
    assert "file_content_read" in negatives["file_content_read"]["failures"]
    assert "dataset_rows_loaded" in negatives["dataset_rows_loaded"]["failures"]
    assert "arxiv_accessed" in negatives["arxiv_accessed"]["failures"]
    assert "ticket_instance_materialized" in negatives["ticket_instance_materialized"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9146_keeps_inventory_and_execution_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["candidate_locator_design_audited"] is True
    assert metrics["candidate_locator_executed"] is False
    assert metrics["path_inventory_materialized"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["ticket_instance_materialized"] is False
    assert metrics["real_input_authorized_now"] is False
    assert metrics["real_judge_rows_used"] == 0
    assert metrics["real_ranker_rows_used"] == 0
    assert metrics["real_route_cards_materialized"] == 0
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["cleanup_authorized_now"] is False


def test_stage9146_bad_live_registry_fails() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9145" in audit["failures"]
