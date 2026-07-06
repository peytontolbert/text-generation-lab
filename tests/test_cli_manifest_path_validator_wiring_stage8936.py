from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8936_cli_manifest_path_validator_wiring import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)


def registry(latest: int = 8935) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8936_audit_confirms_cli_wiring_and_tests() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["cli_imports_validator"] is True
    assert audit["checks"]["cli_validates_manifest_mode_input"] is True
    assert audit["checks"]["cli_rejects_failed_path_card"] is True
    assert audit["checks"]["test_rejects_unfocused_input_path"] is True


def test_stage8936_audit_keeps_all_authority_closed() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["training_remains_blocked"] is True
    assert audit["checks"]["data_mining_remains_blocked"] is True
    assert audit["checks"]["runtime_remains_blocked"] is True
    assert all(value is False for value in audit["authority"].values())


def test_stage8936_validation_rejects_bad_frontier_or_open_authority() -> None:
    audit = build_audit(registry())
    assert validate_audit(audit, registry()) == []
    bad_audit = build_audit(registry())
    bad_audit["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad_audit, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(audit, registry(latest=9999))
