from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9156_repo_local_inventory_final_pre_execution_authorization_design import (  # noqa: E402
    AUTHORIZED_FUTURE_OUTPUTS_ONLY,
    CURRENT_BLOCKERS,
    FORBIDDEN_DURING_EXECUTION,
    NEGATIVE_CASES,
    REQUIRED_BEFORE_EXECUTION,
    build_summary,
    run_negative_cases,
    validate_design,
)


def test_stage9156_design_passes_and_does_not_authorize_execution() -> None:
    summary = build_summary()
    design = summary["design"]
    metrics = summary["metrics"]

    assert summary["passed"] is True
    assert validate_design(design) == []
    assert metrics["inventory_execution_authorized_now"] is False
    assert metrics["inventory_execution_authorized_next"] is False
    assert "explicit_user_inventory_execution_request_missing" in design["current_blockers"]
    assert "access_arxiv" in design["forbidden_during_execution"]
    assert not any(summary["authority"].values())


def test_stage9156_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9155_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "missing_required_before_execution:explicit_user_inventory_execution_request" in negatives["missing_required_before_execution"]["failures"]
    assert "missing_current_blocker:explicit_user_inventory_execution_request_missing" in negatives["missing_current_blocker"]["failures"]
    assert "missing_authorized_future_output:metadata_only_path_inventory.json" in negatives["missing_authorized_future_output"]["failures"]
    assert "missing_forbidden_during_execution:access_arxiv" in negatives["missing_forbidden_during_execution"]["failures"]
    assert "inventory_execution_authorized_now" in negatives["execution_authorized_now"]["failures"]
    assert "inventory_execution_authorized_next" in negatives["execution_authorized_next"]["failures"]
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


def test_stage9156_declares_pre_execution_contract_shape() -> None:
    summary = build_summary()
    design = summary["design"]

    assert set(REQUIRED_BEFORE_EXECUTION).issubset(set(design["required_before_execution"]))
    assert set(CURRENT_BLOCKERS).issubset(set(design["current_blockers"]))
    assert set(AUTHORIZED_FUTURE_OUTPUTS_ONLY).issubset(set(design["authorized_future_outputs_only"]))
    assert set(FORBIDDEN_DURING_EXECUTION).issubset(set(design["forbidden_during_execution"]))


def test_stage9156_keeps_all_execution_paths_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert metrics["design_only"] is True
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
