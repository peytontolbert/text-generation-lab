from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9176_trainer_setup_emit_instance_audit import (  # noqa: E402
    build_audit,
    registry,
)


def test_stage9176_audit_passes() -> None:
    audit = build_audit(registry())
    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9175_passed"] is True
    assert audit["checks"]["registry_frontier_stage9175"] is True
    assert audit["checks"]["emit_instance_not_open_now"] is True
    assert audit["checks"]["outputs_not_emitted_now"] is True
