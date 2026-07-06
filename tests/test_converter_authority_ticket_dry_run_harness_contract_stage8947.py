from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8947_converter_authority_ticket_dry_run_harness_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    AUTHORITY_TICKET_SCHEMA,
    DRY_RUN_HARNESS_STEPS,
    FORBIDDEN_WITHOUT_FUTURE_TICKET,
    build_contract,
    validate_contract,
)


def registry(latest: int = 8946) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8947_records_future_ticket_schema_and_noop_harness() -> None:
    contract = build_contract(registry())
    assert len(AUTHORITY_TICKET_SCHEMA) >= 10
    assert len(DRY_RUN_HARNESS_STEPS) >= 9
    assert len(FORBIDDEN_WITHOUT_FUTURE_TICKET) >= 8
    assert contract["metrics"]["future_ticket_present"] is False
    assert contract["metrics"]["future_ticket_validated"] is False
    assert contract["placeholder_ticket"]["allowed_operations"] == []


def test_stage8947_keeps_checkpoint_converter_runtime_and_training_closed() -> None:
    contract = build_contract(registry())
    assert contract["metrics"]["checkpoint_open_authorized"] is False
    assert contract["metrics"]["real_weight_read_authorized"] is False
    assert contract["metrics"]["converter_execution_authorized"] is False
    assert contract["metrics"]["checkpoint_write_authorized"] is False
    assert contract["metrics"]["model_execution_authorized_now"] is False
    assert contract["metrics"]["training_authorized"] is False
    assert all(value is False for value in contract["authority"].values())


def test_stage8947_validation_rejects_ticket_operations_or_open_authority() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []
    bad_ops = build_contract(registry())
    bad_ops["placeholder_ticket"]["allowed_operations"] = ["decode_real_packed_bitnet"]
    assert "placeholder_ticket_allows_operations" in validate_contract(bad_ops, registry())
    bad_authority = build_contract(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
