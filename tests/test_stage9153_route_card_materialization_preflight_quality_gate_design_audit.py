from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9153_route_card_materialization_preflight_quality_gate_design_audit import (  # noqa: E402
    AUDIT_NEGATIVE_CASES,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9153_audit_passes_with_stage9152_frontier() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9152_passed"] is True
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["quality_gate_before_route_write"] is True
    assert audit["checks"]["quality_gate_before_route_to_loss"] is True


def test_stage9153_rejects_all_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(AUDIT_NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "candidate_quality_gate_not_attached" in negatives["quality_gate_not_attached"]["failures"]
    assert "quality_gate_not_before_route_cards_write" in negatives["missing_quality_gate_validate_before_route_write"]["failures"]
    assert "inventory_runner_executed_now" in negatives["inventory_executed_now"]["failures"]
    assert "metadata_path_inventory_loaded_now" in negatives["metadata_inventory_loaded_now"]["failures"]
    assert "candidate_rows_loaded" in negatives["candidate_rows_loaded"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9153_rejects_bad_registry_frontier() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9152" in audit["failures"]


def test_stage9153_keeps_inventory_route_and_training_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

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
