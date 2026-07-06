from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8930_targeted_compiler_gap_tests_readiness import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8929, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_readiness_records_targeted_modules_and_capabilities() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["targeted_test_file_present"] is True
    assert audit["checks"]["all_targeted_modules_present"] is True
    assert audit["checks"]["capabilities_recorded"] is True
    assert audit["metrics"]["targeted_capabilities"] == 4


def test_readiness_keeps_training_and_mining_blocked() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["training_remains_blocked"] is True
    assert audit["checks"]["data_mining_remains_blocked"] is True
    assert audit["checks"]["runtime_remains_blocked"] is True
    assert all(value is False for value in audit["authority"].values())


def test_validation_rejects_bad_frontier_or_authority() -> None:
    assert validate_audit(build_audit(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_audit(build_audit(registry()), bad_registry)
    bad_audit = build_audit(registry())
    bad_audit["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad_audit, registry())
