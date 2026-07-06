from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8935_audit_only_manifest_path_validator import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)


def registry(latest: int = 8934) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8935_audit_accepts_local_manifest_and_rejects_risky_paths() -> None:
    audit = build_audit(registry())
    assert audit["accepted_example"]["allowed"] is True
    assert audit["rejected_examples"]["arxiv"]["allowed"] is False
    assert audit["rejected_examples"]["data_outside_repo"]["allowed"] is False
    assert audit["checks"]["rejects_arxiv"] is True
    assert audit["checks"]["rejects_data_outside_repo"] is True
    assert audit["checks"]["rejects_traversal"] is True
    assert audit["checks"]["rejects_glob"] is True
    assert audit["checks"]["rejects_remote_uri"] is True


def test_stage8935_audit_keeps_authority_and_training_closed() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["training_remains_blocked"] is True
    assert audit["checks"]["data_mining_remains_blocked"] is True
    assert audit["checks"]["runtime_remains_blocked"] is True
    assert all(value is False for value in audit["authority"].values())


def test_stage8935_validation_rejects_open_authority_or_bad_frontier() -> None:
    audit = build_audit(registry())
    assert validate_audit(audit, registry()) == []
    bad_audit = build_audit(registry())
    bad_audit["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad_audit, registry())
    assert "unexpected_registry_frontier:9999" in validate_audit(audit, registry(latest=9999))
