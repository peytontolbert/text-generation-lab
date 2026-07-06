from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8952_converter_test_spec_promotion_gate import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_WITHOUT_PROMOTION_TICKET,
    PROMOTION_REQUIREMENTS,
    build_gate,
    validate_gate,
)


def registry(latest: int = 8951) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8952_gate_requires_future_ticket_before_runnable_specs() -> None:
    gate = build_gate(registry())
    assert len(PROMOTION_REQUIREMENTS) >= 10
    assert len(FORBIDDEN_WITHOUT_PROMOTION_TICKET) >= 8
    assert gate["metrics"]["source_test_spec_rows"] >= 5
    assert gate["metrics"]["future_ticket_present"] is False
    assert gate["metrics"]["runnable_specs_authorized"] == 0


def test_stage8952_keeps_checkpoint_tensor_model_and_training_closed() -> None:
    gate = build_gate(registry())
    assert gate["metrics"]["test_files_written"] == 0
    assert gate["metrics"]["checkpoint_open_authorized"] is False
    assert gate["metrics"]["real_tensor_read_authorized"] is False
    assert gate["metrics"]["packed_decode_authorized"] is False
    assert gate["metrics"]["model_execution_authorized_now"] is False
    assert gate["metrics"]["training_authorized"] is False
    assert all(value is False for value in gate["authority"].values())


def test_stage8952_validation_rejects_open_authority_or_runnable_specs() -> None:
    gate = build_gate(registry())
    assert validate_gate(gate, registry()) == []
    bad = build_gate(registry())
    bad["metrics"]["runnable_specs_authorized"] = 1
    assert "runnable_specs_authorized" in validate_gate(bad, registry())
    bad_authority = build_gate(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_gate(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_gate(gate, registry(latest=9999))
