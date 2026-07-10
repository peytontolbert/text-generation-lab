from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9156_metadata_inventory_final_authorization_blocker_contract import (  # noqa: E402
    AUTHORIZATION_BOUNDARIES,
    NEGATIVE_CASES,
    REQUIRED_PREAUTH_EVIDENCE,
    build_summary,
    run_negative_cases,
    validate_contract,
)


def test_stage9156_contract_passes_and_lists_preauth_evidence() -> None:
    summary = build_summary()
    contract = summary["contract"]

    assert summary["passed"] is True
    assert validate_contract(contract) == []
    assert set(REQUIRED_PREAUTH_EVIDENCE).issubset(set(contract["required_preauth_evidence"]))
    assert set(AUTHORIZATION_BOUNDARIES).issubset(set(contract["authorization_boundaries"]))
    assert "stage9155_repo_local_inventory_single_run_ticket_instance_design_audit_passed" in contract["required_preauth_evidence"]
    assert "registry_has_no_open_authority_counts" in contract["required_preauth_evidence"]
    assert "must_not_authorize_route_card_materialization" in contract["authorization_boundaries"]
    assert "must_not_read_file_contents" in contract["authorization_boundaries"]


def test_stage9156_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_preauth_evidence:stage9155_repo_local_inventory_single_run_ticket_instance_design_audit_passed" in negatives["missing_preauth_evidence"]["failures"]
    assert "missing_authorization_boundary:must_not_authorize_route_card_materialization" in negatives["missing_authorization_boundary"]["failures"]
    assert "metadata_inventory_execution_authorized_now" in negatives["execution_authorized_now"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_card_materialization_authorized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_mask_materialization_authorized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_authorized"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_authorized"]["failures"]
    assert "model_forward_attempted" in negatives["model_forward_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "file_content_read" in negatives["file_content_read_allowed"]["failures"]
    assert "arxiv_accessed" in negatives["arxiv_access_allowed"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9156_keeps_execution_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]
    contract_metrics = summary["contract"]["metrics"]

    assert metrics["contract_only"] is True
    assert contract_metrics["metadata_inventory_execution_authorized_now"] is False
    assert contract_metrics["metadata_inventory_execution_authorized_next"] is False
    assert contract_metrics["single_run_ticket_instantiated_now"] is False
    assert contract_metrics["inventory_runner_executed_now"] is False
    assert contract_metrics["metadata_path_inventory_loaded_now"] is False
    assert contract_metrics["path_inventory_rows_loaded"] == 0
    assert contract_metrics["candidate_rows_loaded"] == 0
    assert contract_metrics["file_content_read"] is False
    assert contract_metrics["json_parsed"] is False
    assert contract_metrics["jsonl_rows_counted"] is False
    assert contract_metrics["dataset_rows_loaded"] is False
    assert contract_metrics["arxiv_accessed"] is False
    assert contract_metrics["external_root_accessed"] is False
    assert contract_metrics["route_cards_materialized_now"] is False
    assert contract_metrics["loss_mask_cards_materialized_now"] is False
    assert contract_metrics["compiler_handoff_ready_now"] is False
    assert contract_metrics["trainer_executed_now"] is False
    assert contract_metrics["model_forward_attempted"] is False
    assert contract_metrics["training_authorized"] is False
    assert contract_metrics["decoder_ce_authorized"] is False
    assert contract_metrics["denoise_ce_authorized"] is False
    assert contract_metrics["runtime_authorized_flag"] is False
    assert contract_metrics["harness_authorized_flag"] is False
    assert not any(summary["authority"].values())
