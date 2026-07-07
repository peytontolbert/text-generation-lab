from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9168_trainer_setup_materializer_wrapper_ticket_instance_audit import (  # noqa: E402
    build_audit,
    registry,
)


def test_stage9168_audit_passes() -> None:
    audit = build_audit(registry())
    assert audit["passed"] is True
    assert audit["failures"] == []
    assert audit["checks"]["source_stage9167_passed"] is True
    assert audit["checks"]["registry_frontier_stage9167"] is True
    assert audit["checks"]["trainer_input_blocked"] is True
    assert audit["checks"]["model_input_rows_blocked"] is True
