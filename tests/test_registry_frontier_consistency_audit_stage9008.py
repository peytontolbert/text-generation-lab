from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9008_registry_frontier_consistency_audit import (  # noqa: E402
    ALLOWED_DUPLICATE_STAGE_IDS,
    AUTHORITY_CLOSED,
    FORBIDDEN_INTERPRETATIONS,
    REQUIRED_FRONTIER_INVARIANTS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {
        "rows": [
            {"stage": 1, "stage_name": "stage1_a", "passed": True, "authority": dict(AUTHORITY_CLOSED)},
            {"stage": 8981, "stage_name": "stage8981_a", "passed": True, "authority": dict(AUTHORITY_CLOSED)},
            {"stage": 8981, "stage_name": "stage8981_b", "passed": True, "authority": dict(AUTHORITY_CLOSED)},
        ],
        "metrics": {"latest_stage": 8981, "registry_rows": 3, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}},
    }


def test_stage9008_records_frontier_invariants_and_duplicate_policy() -> None:
    card = build_audit(registry())
    assert 8981 in ALLOWED_DUPLICATE_STAGE_IDS
    assert "latest_stage_points_to_highest_stage_row" in REQUIRED_FRONTIER_INVARIANTS
    assert "latest_stage_means_training_ready" in FORBIDDEN_INTERPRETATIONS
    assert card["metrics"]["duplicate_stage_ids"] == 1
    assert card["metrics"]["unexpected_duplicate_stage_ids"] == 0


def test_stage9008_keeps_registry_audit_non_authorizing() -> None:
    card = build_audit(registry())
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["trainer_dry_run_execution_authorized_now"] is False
    assert card["metrics"]["promotion_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9008_validation_rejects_open_authority_or_execution_flags() -> None:
    assert validate_audit(build_audit(registry())) == []
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_audit(unsafe)


def test_stage9008_records_unexpected_duplicates_as_cleanup_blocker() -> None:
    bad = registry()
    bad["rows"].append({"stage": 2, "stage_name": "stage2_a", "passed": True, "authority": dict(AUTHORITY_CLOSED)})
    bad["rows"].append({"stage": 2, "stage_name": "stage2_b", "passed": True, "authority": dict(AUTHORITY_CLOSED)})
    bad["metrics"]["registry_rows"] = len(bad["rows"])
    bad["metrics"]["latest_stage"] = 8981
    card = build_audit(bad)
    assert card["metrics"]["unexpected_duplicate_stage_ids"] == 1
    assert card["metrics"]["duplicate_cleanup_required"] is True
    assert validate_audit(card) == []
