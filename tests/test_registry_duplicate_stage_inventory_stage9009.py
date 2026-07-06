from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9009_registry_duplicate_stage_inventory import (  # noqa: E402
    AUTHORITY_CLOSED,
    classify_stage,
    duplicate_inventory,
    build_inventory,
    validate_inventory,
)


def registry() -> dict[str, object]:
    return {
        "rows": [
            {"stage": 8603, "stage_name": "stage8603_a", "passed": True, "authority": dict(AUTHORITY_CLOSED), "path": "a"},
            {"stage": 8603, "stage_name": "stage8603_b", "passed": True, "authority": dict(AUTHORITY_CLOSED), "path": "b"},
            {"stage": 8991, "stage_name": "stage8991_a", "passed": True, "authority": dict(AUTHORITY_CLOSED), "path": "c"},
            {"stage": 8991, "stage_name": "stage8991_b", "passed": True, "authority": dict(AUTHORITY_CLOSED), "path": "d"},
        ],
        "metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}},
    }


def test_stage9009_classifies_duplicate_recovery_bands() -> None:
    assert classify_stage(8603) == "early_recovery_support_modules"
    assert classify_stage(8810) == "mid_recovery_training_modules"
    assert classify_stage(8977) == "late_recovery_ticket_modules"
    assert classify_stage(8991) == "explicitly_allowed_duplicate"
    assert classify_stage(9100) == "unexpected_outside_recovery_bands"


def test_stage9009_inventory_keeps_rows_without_mutation() -> None:
    inv = duplicate_inventory(registry())
    assert len(inv["duplicates"]) == 2
    assert inv["duplicates"][0]["count"] == 2
    card = build_inventory(registry())
    assert card["metrics"]["inventory_only_no_mutation"] is True
    assert card["metrics"]["registry_rows_mutated_now"] is False
    assert card["metrics"]["renumbering_authorized_now"] is False


def test_stage9009_validation_rejects_mutation_or_authority() -> None:
    assert validate_inventory(build_inventory(registry())) == []
    mutated = build_inventory(registry())
    mutated["metrics"]["registry_rows_deleted_now"] = True
    assert "registry_rows_deleted_now" in validate_inventory(mutated)
    opened = build_inventory(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_inventory(opened)
