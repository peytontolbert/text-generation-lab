from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9014_duplicate_resolution_preview_review_gate import (  # noqa: E402
    AUTHORITY_CLOSED,
    review_operations,
    build_gate,
    validate_gate,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}, "rows": []}


def test_stage9014_reviews_alias_only_operations() -> None:
    ops = [{"operation": "add_registry_alias_metadata_only", "alias_id": "a", "proposed_registry_key": "k", "source_summary_path": "p", "apply_now": False, "delete_original_row": False, "preserve_original_row": True}]
    review = review_operations(ops)
    assert review["operation_count"] == 1
    assert review["unsafe_operations"] == 0
    assert review["unique_alias_ids"] is True


def test_stage9014_detects_unsafe_operations() -> None:
    ops = [{"operation": "delete", "alias_id": "a", "proposed_registry_key": "k", "source_summary_path": "p", "apply_now": True, "delete_original_row": True, "preserve_original_row": False}]
    review = review_operations(ops)
    assert review["unsafe_operations"] == 1


def test_stage9014_gate_keeps_apply_closed() -> None:
    card = build_gate(registry())
    assert card["metrics"]["apply_authorized_now"] is False
    assert card["metrics"]["registry_written_now"] is False
    assert card["metrics"]["training_authorized"] is False
    assert validate_gate(card) == []
    unsafe = build_gate(registry())
    unsafe["metrics"]["alias_diff_applied_now"] = True
    assert "alias_diff_applied_now" in validate_gate(unsafe)
    opened = build_gate(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_gate(opened)
