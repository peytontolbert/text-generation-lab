from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8951_converter_acceptance_test_generator_contract_retry import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    validate_contract,
)


def registry(latest: int = 8950) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8951_recovers_metadata_only_generator_after_frontier_normalization() -> None:
    contract = build_contract(registry())
    assert contract["source_stage"] == 8950
    assert contract["fixture_source_stage"] == 8948
    assert contract["metrics"]["source_fixture_rows"] >= 5
    assert contract["metrics"]["test_spec_rows"] == contract["metrics"]["source_fixture_rows"]
    assert contract["metrics"]["generated_specs_runnable_now"] == 0


def test_stage8951_keeps_converter_checkpoint_model_and_training_closed() -> None:
    contract = build_contract(registry())
    assert contract["metrics"]["python_test_files_written"] == 0
    assert contract["metrics"]["converter_code_written"] is False
    assert contract["metrics"]["checkpoint_open_authorized"] is False
    assert contract["metrics"]["packed_decode_authorized"] is False
    assert contract["metrics"]["model_execution_authorized_now"] is False
    assert contract["metrics"]["training_authorized"] is False
    assert all(value is False for value in contract["authority"].values())


def test_stage8951_validation_rejects_runnable_specs_or_bad_frontier() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []
    bad_runnable = build_contract(registry())
    bad_runnable["metrics"]["generated_specs_runnable_now"] = 1
    assert "generated_specs_runnable_now" in validate_contract(bad_runnable, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
