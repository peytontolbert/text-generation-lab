from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9162_trainer_dry_run_input_readiness_refresh_after_loss_mask_preflight import (  # noqa: E402
    NEGATIVE_CASES,
    build_card,
    build_summary,
    run_negative_cases,
    validate_card,
)


def test_stage9162_card_passes_and_blocks_trainer_outputs() -> None:
    card = build_card({"passed": True})

    assert validate_card(card) == []
    assert card["metrics"]["refresh_only"] is True
    assert card["metrics"]["loss_mask_cards_materialized_now"] is False
    assert card["metrics"]["trainer_input_materialized_now"] is False
    assert card["metrics"]["trainer_dry_run_ready_now"] is False
    assert card["metrics"]["trainer_contract_only_invoked_now"] is False
    assert "trainer_dry_run_input.json" in card["blocked_outputs"]
    assert "trainer_contract_only_output.json" in card["blocked_outputs"]
    assert "model_input_rows.jsonl" in card["blocked_outputs"]


def test_stage9162_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9161_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "missing_required_input:loss_mask_cards.jsonl" in negatives["missing_required_input"]["failures"]
    assert "missing_required_assertion:no_model_forward_during_input_readiness" in negatives["missing_required_assertion"]["failures"]
    assert "missing_hard_stop:dry_run_stops_before_model_forward" in negatives["missing_hard_stop"]["failures"]
    assert "missing_telemetry_stub:row_field_logits.jsonl" in negatives["missing_telemetry_stub"]["failures"]
    assert "missing_blocked_output:trainer_dry_run_input.json" in negatives["missing_blocked_output"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "trainer_input_materialized_now" in negatives["trainer_input_materialized"]["failures"]
    assert "trainer_dry_run_ready_now" in negatives["trainer_dry_run_ready"]["failures"]
    assert "trainer_executed_now" in negatives["trainer_executed"]["failures"]
    assert "model_forward_attempted" in negatives["model_forward"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9162_declares_loss_mask_input_readiness_shape() -> None:
    card = build_card({"passed": True})

    assert "loss_mask_cards.jsonl" in card["required_inputs"]
    assert "trainer_dry_run_input_schema_lock.json" in card["required_inputs"]
    assert "loss_mask_cards_materialized_and_audited_before_trainer_input" in card["required_assertions"]
    assert "trainer_input_materialization_requires_separate_ticket" in card["required_assertions"]
    assert "dry_run_stops_before_model_forward" in card["documented_hard_stops"]
    assert "row_field_logits.jsonl" in card["required_telemetry_stubs"]
    assert card["metrics"]["model_input_rows_now"] == 0


def test_stage9162_keeps_all_execution_and_training_paths_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert summary["passed"] is True
    assert metrics["model_forward_attempted"] is False
    assert metrics["model_weights_loaded"] is False
    assert metrics["optimizer_created"] is False
    assert metrics["backward_called"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(summary["authority"].values())
