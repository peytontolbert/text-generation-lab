from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9007_locked_manifest_materialization_ticket_design import (  # noqa: E402
    AUTHORITY_CLOSED,
    FUTURE_OUTPUTS,
    LOSS_MASK_DEFAULTS,
    MATERIALIZATION_CHECKS,
    build_design,
    validate_design,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9007_records_future_manifest_outputs() -> None:
    card = build_design(registry())
    for output in ["locked_tiny_training_manifest.jsonl", "loss_mask_card.json", "manifest_schema_lock.json", "trainer_contract_dry_run_input.json", "contamination_and_leakage_proof.json"]:
        assert output in FUTURE_OUTPUTS
    assert card["metrics"]["future_outputs"] >= 6


def test_stage9007_keeps_loss_masks_and_execution_closed() -> None:
    card = build_design(registry())
    assert all(value is False for value in LOSS_MASK_DEFAULTS.values())
    assert "no_row_body_materialization" in MATERIALIZATION_CHECKS
    assert "all_loss_masks_default_false" in MATERIALIZATION_CHECKS
    assert card["metrics"]["manifest_materialized_now"] is False
    assert card["metrics"]["trainer_dry_run_execution_authorized_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9007_validation_rejects_manifest_or_authority_side_effects() -> None:
    assert validate_design(build_design(registry())) == []
    emitted = build_design(registry())
    emitted["metrics"]["manifest_emitted_now"] = True
    assert "manifest_emitted_now" in validate_design(emitted)
    opened = build_design(registry())
    opened["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_design(opened)
    bad_mask = build_design(registry())
    bad_mask["loss_mask_defaults"]["train_decoder_ce"] = True
    assert "loss_mask_defaults_open" in validate_design(bad_mask)
