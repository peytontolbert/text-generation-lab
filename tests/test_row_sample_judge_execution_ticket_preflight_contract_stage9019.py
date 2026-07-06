from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9019_row_sample_judge_execution_ticket_preflight_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_INPUT_ARTIFACTS,
    REQUIRED_OUTPUT_ARTIFACTS,
    REQUIRED_TICKET_FIELDS,
    TICKET_TEMPLATE,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9019_records_future_execution_ticket_schema() -> None:
    card = build_contract(registry())
    assert len(REQUIRED_TICKET_FIELDS) >= 17
    assert len(REQUIRED_INPUT_ARTIFACTS) == 4
    assert len(REQUIRED_OUTPUT_ARTIFACTS) == 5
    for field in REQUIRED_TICKET_FIELDS:
        assert field in card["ticket_template"]


def test_stage9019_ticket_template_keeps_materialization_closed() -> None:
    card = build_contract(registry())
    template = card["ticket_template"]
    assert template["row_body_access_policy"]["read_row_bodies"] is False
    assert template["source_body_access_policy"]["read_repository_source_bodies"] is False
    assert template["decoder_loss_policy"]["decoder_ce_authorized"] is False
    assert template["denoise_loss_policy"]["denoise_ce_authorized"] is False
    assert template["trainer_policy"]["training_authorized"] is False
    assert all(value is False for value in template["authority"].values())
    assert all(value is False for value in card["authority"].values())


def test_stage9019_forbids_execution_training_and_body_access() -> None:
    card = build_contract(registry())
    assert "READ_ROW_BODY_TEXT" in FORBIDDEN_OPERATIONS
    assert "RUN_MODEL" in FORBIDDEN_OPERATIONS
    assert "RUN_RUNTIME" in FORBIDDEN_OPERATIONS
    assert "AUTHORIZE_DECODER_CE" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["execution_ticket_instantiated_now"] is False
    assert card["metrics"]["row_sample_judge_executed_now"] is False
    assert card["metrics"]["judge_outputs_materialized_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9019_validation_rejects_open_authority_or_execution_side_effects() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["ticket_template"] = dict(TICKET_TEMPLATE)
    opened["ticket_template"]["authority"] = dict(TICKET_TEMPLATE["authority"])
    opened["ticket_template"]["authority"]["runtime_authorized"] = True
    assert "template_authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["row_sample_judge_executed_now"] = True
    assert "row_sample_judge_executed_now" in validate_contract(unsafe)
