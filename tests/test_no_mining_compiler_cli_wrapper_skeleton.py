from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8933_no_mining_compiler_cli_wrapper_skeleton import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8932, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_wrapper_skeleton_audit_finds_script_flags_and_tests() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["wrapper_script_present"] is True
    assert audit["checks"]["wrapper_test_present"] is True
    assert audit["checks"]["required_flags_present"] is True
    assert audit["checks"]["forbidden_flags_declared"] is True
    assert audit["checks"]["forbidden_flag_rejection_present"] is True


def test_wrapper_skeleton_keeps_loss_and_execution_closed() -> None:
    audit = build_audit(registry())
    assert audit["checks"]["decoder_ce_closed_in_wrapper"] is True
    assert audit["checks"]["denoise_ce_closed_in_wrapper"] is True
    assert audit["checks"]["runtime_closed_in_wrapper"] is True
    assert audit["checks"]["training_remains_blocked"] is True
    assert audit["checks"]["data_mining_remains_blocked"] is True
    assert audit["checks"]["model_execution_remains_blocked"] is True
    assert all(value is False for value in audit["authority"].values())


def test_validation_rejects_bad_frontier_or_open_authority() -> None:
    assert validate_audit(build_audit(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_audit(build_audit(registry()), bad_registry)
    bad_audit = build_audit(registry())
    bad_audit["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(bad_audit, registry())
