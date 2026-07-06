from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8949_converter_acceptance_test_generator_contract import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_GENERATOR_OUTPUTS,
    GENERATOR_OUTPUT_FIELDS,
    build_contract,
    build_test_spec_rows,
    source_acceptance_rows,
    validate_contract,
)


def registry(latest: int = 8948) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8949_generates_metadata_only_test_specs_from_fixture_specs() -> None:
    source_rows = source_acceptance_rows()
    test_rows = build_test_spec_rows(source_rows)
    assert len(source_rows) >= 5
    assert len(test_rows) == len(source_rows)
    assert len(GENERATOR_OUTPUT_FIELDS) >= 8
    assert len(FORBIDDEN_GENERATOR_OUTPUTS) >= 7
    assert all(row["runnable_now"] is False for row in test_rows)
    assert all(row["requires_future_authority_ticket"] is True for row in test_rows)


def test_stage8949_writes_no_runnable_tests_and_keeps_execution_closed() -> None:
    contract = build_contract(registry())
    assert contract["metrics"]["python_test_files_written"] == 0
    assert contract["metrics"]["generated_specs_runnable_now"] == 0
    assert contract["metrics"]["converter_code_written"] is False
    assert contract["metrics"]["checkpoint_open_authorized"] is False
    assert contract["metrics"]["packed_decode_authorized"] is False
    assert contract["metrics"]["model_execution_authorized_now"] is False
    assert contract["metrics"]["training_authorized"] is False
    assert all(value is False for value in contract["authority"].values())


def test_stage8949_validation_rejects_runnable_output_or_open_authority() -> None:
    contract = build_contract(registry())
    assert validate_contract(contract, registry()) == []
    bad_runnable = build_contract(registry())
    bad_runnable["metrics"]["generated_specs_runnable_now"] = 1
    assert "generated_specs_runnable_now" in validate_contract(bad_runnable, registry())
    bad_authority = build_contract(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_contract(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_contract(contract, registry(latest=9999))
