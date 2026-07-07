from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9161_loss_mask_materialization_preflight_audit import (  # noqa: E402
    AUDIT_NEGATIVE_CASES,
    build_audit,
    registry,
    run_negative_cases,
)


def test_stage9161_audit_passes_with_stage9160_frontier() -> None:
    audit = build_audit(registry())

    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9160_passed"] is True
    assert audit["checks"]["base_design_passes"] is True
    assert audit["checks"]["loss_masks_blocked"] is True
    assert audit["checks"]["trainer_input_blocked"] is True
    assert audit["checks"]["registry_frontier_stage9160"] is True


def test_stage9161_rejects_negative_cases() -> None:
    negatives = run_negative_cases()

    assert set(AUDIT_NEGATIVE_CASES) == set(negatives)
    assert all(item["rejected"] for item in negatives.values())
    assert "source_stage9159_not_passed" in negatives["source_stage_missing"]["failures"]
    assert "missing_required_input:route_cards_jsonl_materialized_and_audited" in negatives["missing_required_input"]["failures"]
    assert "missing_preflight_check:decoder_ce_requires_keep_bounded_decoder_and_budget_ok" in negatives["missing_preflight_check"]["failures"]
    assert "missing_blocked_output:loss_mask_cards.jsonl" in negatives["missing_blocked_output"]["failures"]
    assert "missing_blocked_output:trainer_dry_run_input.json" in negatives["missing_trainer_input_block"]["failures"]
    assert "loss_mask_cards_materialized_now" in negatives["loss_masks_materialized"]["failures"]
    assert "trainer_input_materialized_now" in negatives["trainer_input_materialized"]["failures"]
    assert "compiler_handoff_ready_now" in negatives["compiler_handoff_ready"]["failures"]
    assert "trainer_dry_run_ready_now" in negatives["trainer_ready"]["failures"]
    assert "training_authorized" in negatives["training_authorized"]["failures"]
    assert "decoder_ce_authorized" in negatives["decoder_ce_authorized"]["failures"]
    assert "denoise_ce_authorized" in negatives["denoise_ce_authorized"]["failures"]
    assert "runtime_authorized_flag" in negatives["runtime_authorized"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]
    assert "unexpected_registry_frontier:9999" in negatives["bad_registry_frontier"]["failures"]


def test_stage9161_rejects_bad_registry_frontier() -> None:
    audit = build_audit(registry(latest=9999))

    assert audit["passed"] is False
    assert "registry_frontier_stage9160" in audit["failures"]


def test_stage9161_keeps_all_training_paths_closed() -> None:
    audit = build_audit(registry())
    metrics = audit["metrics"]

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
    assert not any(audit["authority"].values())
