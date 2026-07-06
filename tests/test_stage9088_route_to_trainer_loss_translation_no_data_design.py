from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9088_route_to_trainer_loss_translation_no_data_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_INPUTS,
    TRANSLATION_OUTPUTS,
    build_design,
    run_negative_cases,
    validate_design,
)


def registry(latest: int = 9087) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9088_design_records_translation_inputs_and_outputs() -> None:
    design = build_design(registry())
    assert design["checks"]["required_inputs_recorded"] is True
    assert design["checks"]["translation_outputs_recorded"] is True
    assert design["checks"]["translation_keys_cover_route_losses"] is True
    for required in REQUIRED_INPUTS:
        assert required in design["required_inputs"]
    for output in TRANSLATION_OUTPUTS:
        assert output in design["translation_outputs"]


def test_stage9088_rejects_negative_cases() -> None:
    negatives = run_negative_cases()
    assert negatives
    assert all(item["rejected"] for item in negatives.values())
    assert "loss_open_before_translation_ready" in negatives["structured_loss_before_translation_ready"]["failures"]
    assert "translation_ready_missing_required_inputs" in negatives["translation_ready_missing_route_card_audit_output"]["failures"]
    assert "forbidden_trainer_loss_open:decoder_ce" in negatives["decoder_ce_open"]["failures"]
    assert "forbidden_trainer_loss_open:denoise_ce" in negatives["denoise_ce_open"]["failures"]
    assert "forbidden_trainer_loss_open:runtime_reward" in negatives["runtime_reward_open"]["failures"]
    assert "trainer_dry_run_ready_not_allowed_by_design" in negatives["trainer_dry_run_ready"]["failures"]
    assert "model_input_ready_not_allowed_by_design" in negatives["model_input_ready"]["failures"]
    assert "authority_open" in negatives["authority_open"]["failures"]


def test_stage9088_keeps_translation_and_training_closed() -> None:
    design = build_design(registry())
    metrics = design["metrics"]
    assert metrics["translation_ready_now"] is False
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["trainer_dry_run_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["training_authorized"] is False
    assert not any(design["authority"].values())


def test_stage9088_validation_rejects_open_translation_or_bad_frontier() -> None:
    design = build_design(registry())
    assert validate_design(design, registry()) == []
    bad = build_design(registry())
    bad["metrics"]["translation_ready_now"] = True
    assert "translation_ready_now" in validate_design(bad, registry())
    bad_rows = build_design(registry())
    bad_rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_design(bad_rows, registry())
    bad_authority = build_design(registry())
    bad_authority["authority"]["decoder_ce_training_authorized_next"] = True
    assert "authority_open" in validate_design(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_design(design, registry(latest=9999))
