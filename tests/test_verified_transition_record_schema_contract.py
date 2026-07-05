from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8899_verified_transition_record_schema_contract import (
    ACTION_SPACE,
    AUTHORITY_CLOSED,
    LOSS_MASK_FIELDS,
    REQUIRED_TOP_LEVEL_FIELDS,
    build_loss_contract,
    build_schema,
    validate_schema,
)


def test_schema_contains_core_transition_fields() -> None:
    schema = build_schema()
    required = set(schema["required_top_level_fields"])
    for field in ["state_before", "retrieval_context", "observation", "action", "verifier_result", "state_after", "reward_signal", "loss_mask"]:
        assert field in required
    assert schema["schema_version"] == "verified_transition_record_v1"
    assert "REPAIR_PATCH" in ACTION_SPACE
    assert "FINISH_VERIFIED" in ACTION_SPACE


def test_authority_and_loss_masks_default_closed() -> None:
    schema = build_schema()
    loss_contract = build_loss_contract()
    assert schema["authority_default"] == AUTHORITY_CLOSED
    assert all(value is False for value in schema["authority_default"].values())
    assert set(loss_contract["default_loss_mask"]) == set(LOSS_MASK_FIELDS)
    assert all(value is False for value in loss_contract["default_loss_mask"].values())
    assert "train_runtime_reward" in loss_contract["forbidden_without_explicit_future_authority"]


def test_schema_validation_rejects_open_registry_authority() -> None:
    schema = build_schema()
    loss_contract = build_loss_contract()
    registry = {"metrics": {"latest_stage": 8898, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_schema(schema, loss_contract, registry) == []
    registry["metrics"]["authority_counts"]["runtime_authorized"] = 1
    assert "registry_authority_counts_nonzero" in validate_schema(schema, loss_contract, registry)


def test_required_field_list_is_stable_and_nonempty() -> None:
    assert len(REQUIRED_TOP_LEVEL_FIELDS) >= 16
    assert REQUIRED_TOP_LEVEL_FIELDS[0] == "record_id"
    assert REQUIRED_TOP_LEVEL_FIELDS[-1] == "telemetry_contract"
