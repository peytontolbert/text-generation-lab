from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9012_codex_sessions_multidataset_mining_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    DATASET_FAMILIES,
    FORBIDDEN_OPERATIONS,
    NORMALIZED_EVENT_TYPES,
    SPLIT_POLICY,
    build_contract,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9012_records_plural_dataset_families_from_sessions() -> None:
    card = build_contract(registry())
    families = {item["family"] for item in DATASET_FAMILIES}
    assert "next_action_policy" in families
    assert "edit_localization" in families
    assert "patch_operator" in families
    assert "verifier_repair" in families
    assert "outcome_reward" in families
    assert "small_validated_patch_generation" in families
    assert card["metrics"]["dataset_families"] >= 9


def test_stage9012_records_event_schema_and_split_policy() -> None:
    card = build_contract(registry())
    assert "tool_call_exec_command" in NORMALIZED_EVENT_TYPES
    assert "tool_call_apply_patch" in NORMALIZED_EVENT_TYPES
    assert "verification_result" in NORMALIZED_EVENT_TYPES
    assert "split_by_session_id_not_row" in SPLIT_POLICY
    assert "never_train_on_hidden_or_locked_eval_slices" in SPLIT_POLICY
    assert card["metrics"]["normalized_event_types"] >= 15


def test_stage9012_keeps_session_mining_closed() -> None:
    card = build_contract(registry())
    assert "READ_SESSIONS_NOW" in FORBIDDEN_OPERATIONS
    assert "MINE_SESSIONS_NOW" in FORBIDDEN_OPERATIONS
    assert "EMIT_TRAINING_ROWS" in FORBIDDEN_OPERATIONS
    assert card["metrics"]["session_read_authorized_now"] is False
    assert card["metrics"]["session_mining_authorized_now"] is False
    assert card["metrics"]["training_rows_emitted_now"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9012_validation_rejects_authority_or_mining_side_effects() -> None:
    assert validate_contract(build_contract(registry())) == []
    opened = build_contract(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(opened)
    unsafe = build_contract(registry())
    unsafe["metrics"]["session_mining_authorized_now"] = True
    assert "session_mining_authorized_now" in validate_contract(unsafe)
