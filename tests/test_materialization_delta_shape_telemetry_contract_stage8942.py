from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8942_materialization_delta_shape_telemetry_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_DELTA_BUCKETS,
    REQUIRED_FUTURE_ARTIFACTS,
    build_contract,
    is_safe_artifact_name,
    validate_contract,
)


def registry(latest: int = 8941) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_required_future_artifacts_are_safe_and_complete() -> None:
    assert len(REQUIRED_FUTURE_ARTIFACTS) >= 12
    assert len(REQUIRED_DELTA_BUCKETS) >= 6
    assert all(is_safe_artifact_name(name) for name in REQUIRED_FUTURE_ARTIFACTS)
    assert "materialization_authority_ticket.json" in REQUIRED_FUTURE_ARTIFACTS
    assert "checkpoint_write_proof.json" in REQUIRED_FUTURE_ARTIFACTS


def test_stage8942_contract_keeps_materialization_actions_blocked() -> None:
    contract = build_contract(registry())
    assert contract["checks"]["required_future_artifacts_recorded"] is True
    assert contract["metrics"]["tensor_read_authorized"] is False
    assert contract["metrics"]["checkpoint_load_authorized"] is False
    assert contract["metrics"]["checkpoint_write_authorized"] is False
    assert all(value is False for value in contract["authority"].values())


def test_stage8942_validation_rejects_bad_frontier_or_open_authority() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []
    bad_contract = build_contract(registry())
    bad_contract["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_contract, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
