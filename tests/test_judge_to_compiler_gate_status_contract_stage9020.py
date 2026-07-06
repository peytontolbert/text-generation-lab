from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9020_judge_to_compiler_gate_status_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    BLOCKED_LOSS_FIELDS,
    GATE_STATUS_TEMPLATE,
    HARD_BLOCKERS,
    REQUIRED_GATE_STATUS_FIELDS,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9020_records_judge_to_compiler_schema() -> None:
    card = build_contract(registry())
    assert len(REQUIRED_GATE_STATUS_FIELDS) >= 15
    assert card["metrics"]["required_recovered_gate_references"] >= 1
    for field in REQUIRED_GATE_STATUS_FIELDS:
        assert field in card["gate_status_template"]


def test_stage9020_blocks_decoder_denoise_and_unchecked_rows() -> None:
    card = build_contract(registry())
    template = card["gate_status_template"]
    assert template["passed"] is False
    assert "train_decoder_ce" in BLOCKED_LOSS_FIELDS
    assert "train_denoise_ce" in BLOCKED_LOSS_FIELDS
    assert "loss_mask_requests_decoder_or_denoise" in HARD_BLOCKERS
    assert "unjudged_row_in_accept_set" in HARD_BLOCKERS
    assert all(value is False for value in template["authority"].values())


def test_stage9020_keeps_manifest_training_and_execution_closed() -> None:
    card = build_contract(registry())
    assert card["metrics"]["gate_status_materialized_now"] is False
    assert card["metrics"]["manifest_compile_authorized_now"] is False
    assert card["metrics"]["manifest_emitted_now"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["model_execution_attempted"] is False


def test_stage9020_validation_rejects_open_authority_or_loss_leak() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["gate_status_template"] = dict(GATE_STATUS_TEMPLATE)
    opened["gate_status_template"]["authority"] = dict(GATE_STATUS_TEMPLATE["authority"])
    opened["gate_status_template"]["authority"]["runtime_authorized"] = True
    assert "template_authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["gate_status_template"] = dict(GATE_STATUS_TEMPLATE)
    unsafe["gate_status_template"]["blocked_losses"] = ["train_retrieval"]
    failures = validate_contract(unsafe)
    assert "decoder_ce_not_blocked" in failures
    assert "denoise_ce_not_blocked" in failures
