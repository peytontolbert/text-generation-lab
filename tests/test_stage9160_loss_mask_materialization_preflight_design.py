from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9160_loss_mask_materialization_preflight_design import (  # noqa: E402
    BLOCKED_OUTPUTS,
    LOSS_MASK_PREFLIGHT_CHECKS,
    NEGATIVE_CASES,
    REQUIRED_INPUTS_BEFORE_LOSS_MASKS,
    build_summary,
    run_negative_cases,
    validate_design,
)


def test_stage9160_design_passes_and_blocks_materialization() -> None:
    summary = build_summary()
    design = summary["design"]

    assert summary["passed"] is True
    assert validate_design(design) == []
    assert "loss_mask_cards.jsonl" in design["blocked_outputs"]
    assert "trainer_dry_run_input.json" in design["blocked_outputs"]
    assert "route_cards_jsonl_materialized_and_audited" in design["required_inputs_before_loss_masks"]
    assert not any(summary["authority"].values())


def test_stage9160_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9159_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "missing_required_input:route_cards_jsonl_materialized_and_audited" in negatives["missing_required_input"]["failures"]
    assert "missing_preflight_check:decoder_ce_requires_keep_bounded_decoder_and_budget_ok" in negatives["missing_preflight_check"]["failures"]
    assert "missing_blocked_output:loss_mask_cards.jsonl" in negatives["missing_blocked_output"]["failures"]
    assert "missing_loss_mask_field:loss_authority_evidence" in negatives["missing_loss_mask_field"]["failures"]
    assert "missing_disabled_default:runtime_reward" in negatives["missing_disabled_default"]["failures"]
    assert "missing_telemetry:loss_mask_enforcement_audit" in negatives["missing_telemetry"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "trainer_input_materialized_now" in negatives["trainer_input_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_dry_run_ready_now" in negatives["trainer_ready"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9160_declares_preflight_shape() -> None:
    summary = build_summary()
    design = summary["design"]

    assert set(REQUIRED_INPUTS_BEFORE_LOSS_MASKS).issubset(set(design["required_inputs_before_loss_masks"]))
    assert set(LOSS_MASK_PREFLIGHT_CHECKS).issubset(set(design["loss_mask_preflight_checks"]))
    assert set(BLOCKED_OUTPUTS).issubset(set(design["blocked_outputs"]))
    assert "runtime_reward" in design["required_disabled_by_default"]
    assert "loss_mask_enforcement_audit" in design["required_telemetry"]


def test_stage9160_keeps_trainer_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert metrics["design_only"] is True
    assert metrics["metadata_inventory_executed_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["trainer_input_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
