from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9041_operator_detail_training_readiness_gate import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_PASSING_INPUTS,
    TRAINING_READINESS_CONDITIONS,
    build_gate,
    validate_gate,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9041_requires_all_future_validation_inputs() -> None:
    card = build_gate(registry())
    assert set(REQUIRED_PASSING_INPUTS) == {
        "operator_detail_metadata_patch_validation_card.json",
        "operator_detail_field_coverage_card.json",
        "operator_detail_hash_audit.json",
        "operator_detail_no_raw_payload_proof_audit.json",
    }
    assert card["metrics"]["required_passing_inputs"] == 4


def test_stage9041_records_training_readiness_conditions() -> None:
    card = build_gate(registry())
    for condition in [
        "all_108_operator_rows_present",
        "all_6_training_ready_fields_present",
        "no_raw_payload_proof_passed",
        "loss_policy_structured_aux_only_until_separate_training_ticket",
    ]:
        assert condition in TRAINING_READINESS_CONDITIONS
        assert condition in card["training_readiness_conditions"]
    assert card["metrics"]["training_readiness_conditions"] >= 12
    assert validate_gate(card) == []


def test_stage9041_allows_only_future_refs_features_after_pass() -> None:
    card = build_gate(registry())
    assert "attach_operator_detail_refs_to_future_judged_rows" in card["allowed_after_future_pass"]
    assert "enable_operator_detail_metadata_as_nonpayload_features" in card["allowed_after_future_pass"]
    assert "allow_structured_aux_loss_consideration_under_separate_ticket" in card["allowed_after_future_pass"]


def test_stage9041_keeps_training_and_ce_closed() -> None:
    card = build_gate(registry())
    assert card["metrics"]["training_readiness_gate_only"] is True
    assert card["metrics"]["operator_detail_training_ready_now"] is False
    assert card["metrics"]["operator_specific_training_authorized_now"] is False
    assert card["metrics"]["training_rows_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert card["metrics"]["denoise_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9041_validation_rejects_open_authority_or_training_ready_now() -> None:
    opened = build_gate(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_gate(opened)
    unsafe = build_gate(registry())
    unsafe["metrics"]["operator_detail_training_ready_now"] = True
    assert "operator_detail_training_ready_now" in validate_gate(unsafe)
