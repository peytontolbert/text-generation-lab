from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9158_compiler_trainer_no_data_readiness_matrix import (  # noqa: E402
    CURRENT_BLOCKERS,
    NEGATIVE_CASES,
    PIPELINE_GATES,
    REQUIRED_NEXT_NON_EXECUTING_STAGES,
    build_summary,
    run_negative_cases,
    validate_matrix,
)


def test_stage9158_matrix_passes_and_keeps_all_gates_blocked() -> None:
    summary = build_summary()
    matrix = summary["matrix"]

    assert summary["passed"] is True
    assert validate_matrix(matrix) == []
    assert all(not row["opens"] for row in matrix["pipeline_gates"])
    assert "metadata_inventory_not_executed" in matrix["current_blockers"]
    assert "route_cards_not_materialized" in matrix["current_blockers"]
    assert "loss_masks_not_materialized" in matrix["current_blockers"]
    assert not any(summary["authority"].values())


def test_stage9158_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9157_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "missing_pipeline_gate:route_to_loss_translation" in negatives["missing_pipeline_gate"]["failures"]
    assert "missing_current_blocker:route_cards_not_materialized" in negatives["missing_current_blocker"]["failures"]
    assert "missing_next_stage:loss_mask_materialization_preflight_design" in negatives["missing_next_stage"]["failures"]
    assert "metadata_inventory_executed_now" in negatives["metadata_inventory_executed"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "trainer_dry_run_authorized_now" in negatives["trainer_dry_run_authorized"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9158_declares_pipeline_shape() -> None:
    summary = build_summary()
    matrix = summary["matrix"]
    gate_names = {row["gate"] for row in matrix["pipeline_gates"]}

    assert {row["gate"] for row in PIPELINE_GATES}.issubset(gate_names)
    assert set(CURRENT_BLOCKERS).issubset(set(matrix["current_blockers"]))
    assert set(REQUIRED_NEXT_NON_EXECUTING_STAGES).issubset(set(matrix["required_next_non_executing_stages"]))
    assert "metadata_inventory" in gate_names
    assert "route_card_materialization" in gate_names
    assert "route_to_loss_translation" in gate_names
    assert "loss_mask_materialization" in gate_names
    assert "trainer_contract_dry_run" in gate_names
    assert "model_training" in gate_names


def test_stage9158_keeps_compiler_trainer_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert metrics["matrix_only"] is True
    assert metrics["metadata_inventory_executed_now"] is False
    assert metrics["metadata_path_inventory_materialized_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_dry_run_authorized_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
