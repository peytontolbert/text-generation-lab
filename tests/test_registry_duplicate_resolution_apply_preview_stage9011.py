from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9011_registry_duplicate_resolution_apply_preview import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_proposed_alias_diff,
    build_preview,
    validate_preview,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}, "rows": []}


def policy() -> dict[str, object]:
    return {"alias_plan": [{"alias_id": "dup-0001", "recovered_stage_id": 1, "stage_name": "s", "path": "p"}]}


def test_stage9011_builds_preview_operations_only() -> None:
    diff = build_proposed_alias_diff(policy())
    assert len(diff) == 1
    assert diff[0]["operation"] == "add_registry_alias_metadata_only"
    assert diff[0]["apply_now"] is False
    assert diff[0]["delete_original_row"] is False


def test_stage9011_preview_keeps_registry_unmodified() -> None:
    card = build_preview(registry())
    assert card["metrics"]["preview_only_no_mutation"] is True
    assert card["metrics"]["registry_written_now"] is False
    assert card["metrics"]["renumbering_applied_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9011_validation_rejects_apply_or_open_authority() -> None:
    assert validate_preview(build_preview(registry())) == []
    unsafe = build_preview(registry())
    unsafe["metrics"]["registry_written_now"] = True
    assert "registry_written_now" in validate_preview(unsafe)
    bad_op = build_preview(registry())
    if bad_op["proposed_diff"]:
        bad_op["proposed_diff"][0]["apply_now"] = True
        assert "unsafe_proposed_operation" in validate_preview(bad_op)
    opened = build_preview(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_preview(opened)
