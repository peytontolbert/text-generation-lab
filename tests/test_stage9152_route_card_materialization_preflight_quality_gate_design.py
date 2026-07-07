from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9152_route_card_materialization_preflight_quality_gate_design import (  # noqa: E402
    NEGATIVE_CASES,
    OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT,
    PREFLIGHT_SECTIONS,
    REQUIRED_PRECHECKS,
    build_summary,
    run_negative_cases,
    validate_design,
)


def test_stage9152_design_passes_and_attaches_quality_gate() -> None:
    summary = build_summary()
    design = summary["design"]

    assert summary["passed"] is True
    assert validate_design(design) == []
    assert design["quality_gate_attachment"]["required"] is True
    assert design["quality_gate_attachment"]["source_stage"] == 9151
    assert "candidate_quality_gate_guard" in design["preflight_sections"]
    assert "candidate_quality_gate_contract_attached" in design["required_prechecks"]


def test_stage9152_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9150_not_passed" in negatives["source_stage9150_missing"]["failures"]
    assert "source_stage9151_not_passed" in negatives["source_stage9151_missing"]["failures"]
    assert "candidate_quality_gate_not_attached" in negatives["quality_gate_not_attached"]["failures"]
    assert "quality_gate_attachment_not_required" in negatives["quality_gate_not_attached"]["failures"]
    assert "missing_preflight_section:candidate_quality_gate_guard" in negatives["missing_preflight_section"]["failures"]
    assert "missing_required_precheck:candidate_quality_gate_contract_attached" in negatives["missing_required_precheck"]["failures"]
    assert "missing_blocked_output:route_cards.jsonl" in negatives["missing_blocked_output"]["failures"]
    assert "inventory_runner_executed_now" in negatives["inventory_executed_now"]["failures"]
    assert "metadata_path_inventory_loaded_now" in negatives["metadata_inventory_loaded_now"]["failures"]
    assert "path_inventory_rows_loaded" in negatives["metadata_inventory_loaded_now"]["failures"]
    assert "file_content_read" in negatives["file_content_read"]["failures"]
    assert "json_parsed" in negatives["json_parsed"]["failures"]
    assert "jsonl_rows_counted" in negatives["jsonl_rows_counted"]["failures"]
    assert "candidate_rows_loaded" in negatives["candidate_rows_loaded"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9152_keeps_materialization_compiler_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert metrics["design_only"] is True
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
    assert not any(summary["authority"].values())


def test_stage9152_declares_preflight_shape() -> None:
    summary = build_summary()
    design = summary["design"]

    assert set(PREFLIGHT_SECTIONS).issubset(set(design["preflight_sections"]))
    assert set(REQUIRED_PRECHECKS).issubset(set(design["required_prechecks"]))
    assert set(OUTPUTS_BLOCKED_UNTIL_SEPARATE_AUDIT).issubset(set(design["outputs_blocked_until_separate_audit"]))
    assert "route_cards.jsonl" in design["outputs_blocked_until_separate_audit"]
    assert "route_card_materialization_audit.json" in design["outputs_blocked_until_separate_audit"]
