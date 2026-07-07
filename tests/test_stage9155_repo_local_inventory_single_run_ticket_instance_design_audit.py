from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9155_repo_local_inventory_single_run_ticket_instance_design_audit import (  # noqa: E402
    AUDIT_NEGATIVE_CASES,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9155_audit_passes_with_stage9154_frontier() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9154_passed"] is True
    assert audit["checks"]["allowed_roots_exact"] is True
    assert audit["checks"]["forbidden_roots_complete"] is True
    assert audit["checks"]["output_dir_repo_local"] is True
    assert audit["checks"]["execution_not_authorized"] is True


def test_stage9155_rejects_all_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(AUDIT_NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "allowed_roots_not_exact" in negatives["allowed_root_missing"]["failures"]
    assert "missing_forbidden_root:/arxiv" in negatives["arxiv_not_forbidden"]["failures"]
    assert "missing_forbidden_root:/data" in negatives["missing_data_forbidden_root"]["failures"]
    assert "output_dir_not_under_runs_local_artifacts" in negatives["output_dir_not_repo_local"]["failures"]
    assert "metadata_inventory_execution_authorized_now" in negatives["execution_authorized_now"]["failures"]
    assert "route_card_materialization_authorized_now" in negatives["route_card_materialization_authorized_now"]["failures"]
    assert "inventory_runner_executed_now" in negatives["inventory_executed_now"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9155_rejects_bad_registry_frontier() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9154" in audit["failures"]


def test_stage9155_keeps_inventory_route_and_training_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

    assert metrics["ticket_instance_materialized_for_execution"] is False
    assert metrics["metadata_inventory_execution_authorized_now"] is False
    assert metrics["metadata_inventory_execution_authorized_next"] is False
    assert metrics["inventory_runner_executed_now"] is False
    assert metrics["metadata_path_inventory_loaded_now"] is False
    assert metrics["path_inventory_rows_loaded"] == 0
    assert metrics["candidate_rows_loaded"] == 0
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
