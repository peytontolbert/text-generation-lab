from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9159_route_to_loss_readiness_refresh_after_inventory_gates import (  # noqa: E402
    NEGATIVE_CASES,
    READINESS_OUTPUTS_BLOCKED,
    REQUIRED_UPSTREAM_GATES,
    TRANSLATION_BLOCKERS,
    build_summary,
    run_negative_cases,
    validate_card,
)


def test_stage9159_refresh_passes_and_declares_route_to_loss_blockers() -> None:
    summary = build_summary()
    card = summary["card"]

    assert summary["passed"] is True
    assert validate_card(card) == []
    assert set(REQUIRED_UPSTREAM_GATES).issubset(set(card["required_upstream_gates"]))
    assert set(TRANSLATION_BLOCKERS).issubset(set(card["translation_blockers"]))
    assert set(READINESS_OUTPUTS_BLOCKED).issubset(set(card["readiness_outputs_blocked"]))
    assert "route_cards_quality_gate_attached" in card["required_upstream_gates"]
    assert "route_cards_not_materialized" in card["translation_blockers"]
    assert "loss_mask_cards.jsonl" in card["readiness_outputs_blocked"]


def test_stage9159_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "missing_upstream_gate:route_cards_quality_gate_attached" in negatives["missing_upstream_gate"]["failures"]
    assert "missing_translation_blocker:route_cards_not_materialized" in negatives["missing_translation_blocker"]["failures"]
    assert "missing_blocked_output:loss_mask_cards.jsonl" in negatives["missing_blocked_output"]["failures"]
    assert "route_cards_materialized_now" in negatives["route_cards_materialized"]["failures"]
    assert "route_to_loss_translation_ready_now" in negatives["translation_ready"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_dry_run_ready_now" in negatives["trainer_ready"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9159_keeps_route_to_loss_and_training_closed() -> None:
    summary = build_summary()
    metrics = summary["metrics"]

    assert metrics["refresh_only"] is True
    assert metrics["metadata_inventory_executed_now"] is False
    assert metrics["metadata_path_inventory_materialized_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["loss_mask_cards_materialized_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["arxiv_accessed"] is False
    assert metrics["file_content_read"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert not any(summary["authority"].values())
