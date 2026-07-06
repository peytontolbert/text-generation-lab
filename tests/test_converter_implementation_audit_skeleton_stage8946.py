from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8946_converter_implementation_audit_skeleton import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_OPERATIONS,
    REQUIRED_AUDIT_PHASES,
    REQUIRED_FUTURE_AUTHORITY_TICKET_FIELDS,
    build_skeleton,
    validate_skeleton,
)


def registry(latest: int = 8945) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8946_records_converter_audit_skeleton_without_converter_execution() -> None:
    skeleton = build_skeleton(registry())
    assert len(REQUIRED_AUDIT_PHASES) >= 10
    assert len(FORBIDDEN_OPERATIONS) >= 10
    assert len(REQUIRED_FUTURE_AUTHORITY_TICKET_FIELDS) >= 10
    assert skeleton["metrics"]["converter_code_written"] is False
    assert skeleton["metrics"]["converter_execution_authorized"] is False


def test_stage8946_keeps_decode_checkpoint_runtime_and_training_closed() -> None:
    skeleton = build_skeleton(registry())
    assert skeleton["metrics"]["real_packed_decode_authorized"] is False
    assert skeleton["metrics"]["checkpoint_load_authorized"] is False
    assert skeleton["metrics"]["checkpoint_write_authorized"] is False
    assert skeleton["metrics"]["model_execution_authorized_now"] is False
    assert skeleton["metrics"]["training_authorized"] is False
    assert all(value is False for value in skeleton["authority"].values())


def test_stage8946_validation_rejects_open_authority_or_implementation_flags() -> None:
    skeleton = build_skeleton(registry())
    assert validate_skeleton(skeleton, registry()) == []
    bad_authority = build_skeleton(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_skeleton(bad_authority, registry())
    bad_decode = build_skeleton(registry())
    bad_decode["metrics"]["real_packed_decode_authorized"] = True
    assert "real_packed_decode_authorized" in validate_skeleton(bad_decode, registry())
    assert "unexpected_registry_frontier:9999" in validate_skeleton(skeleton, registry(latest=9999))
