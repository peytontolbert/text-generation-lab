from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9199_trainer_contract_ready_recovery_audit import build_audit, registry  # noqa: E402


def test_stage9199_audit_passes() -> None:
    audit = build_audit(registry())
    assert audit["passed"] is True
    assert audit["checks"]["source_stage9198_passed"] is True
    assert audit["checks"]["required_flags_present"] is True
    assert audit["checks"]["required_modes_present"] is True
    assert audit["metrics"]["trainer_contract_ready"] is True
