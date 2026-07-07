from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9172_trainer_setup_materialization_instance_audit import (  # noqa: E402
    build_audit,
    registry,
)


def test_stage9172_audit_passes() -> None:
    audit = build_audit(registry())
    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9171_passed"] is True
    assert audit["checks"]["registry_frontier_stage9171"] is True
    assert audit["checks"]["trainer_input_not_materialized"] is True
    assert audit["checks"]["trainer_not_invoked"] is True
