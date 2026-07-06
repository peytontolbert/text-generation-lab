from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9010_registry_duplicate_resolution_policy import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_alias_plan,
    build_policy,
    validate_policy,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}, "rows": []}


def inventory() -> dict[str, object]:
    return {"duplicates": [{"stage": 1, "count": 2, "stage_names": ["a", "b"], "paths": ["pa", "pb"]}]}


def test_stage9010_builds_preservation_aliases() -> None:
    plan = build_alias_plan(inventory())
    assert len(plan) == 2
    assert plan[0]["alias_id"] == "dup-0001"
    assert plan[0]["preserve_original_stage_id"] is True
    assert plan[0]["apply_now"] is False


def test_stage9010_policy_is_non_mutating() -> None:
    card = build_policy(registry())
    assert card["metrics"]["policy_only_no_mutation"] is True
    assert card["metrics"]["renumbering_applied_now"] is False
    assert card["metrics"]["registry_rows_deleted_now"] is False
    assert card["metrics"]["training_authorized"] is False


def test_stage9010_validation_rejects_mutation_or_open_authority() -> None:
    assert validate_policy(build_policy(registry())) == []
    mutated = build_policy(registry())
    mutated["metrics"]["renumbering_applied_now"] = True
    assert "renumbering_applied_now" in validate_policy(mutated)
    opened = build_policy(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_policy(opened)
    bad_alias = build_policy(registry())
    if bad_alias["alias_plan"]:
        bad_alias["alias_plan"][0]["apply_now"] = True
        assert "alias_apply_now" in validate_policy(bad_alias)
