from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8952_registry_independent_acceptance_generator_recovery import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_contract,
    stale_frontier_rows,
    validate_contract,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8946, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8952_recovers_from_stable_fixture_source_without_latest_pointer() -> None:
    contract = build_contract(registry())
    assert contract["stable_source_stage"] == 8948
    assert contract["metrics"]["source_fixture_rows"] >= 5
    assert contract["metrics"]["test_spec_rows"] == contract["metrics"]["source_fixture_rows"]
    assert contract["metrics"]["stale_frontier_rows"] >= 2
    assert validate_contract(contract) == []


def test_stage8952_records_stale_frontier_rows_as_hygiene_issue() -> None:
    rows = stale_frontier_rows()
    assert len(rows) >= 2
    assert all(row["frontier_only_failure"] for row in rows if row["failures"])


def test_stage8952_keeps_generated_specs_non_runnable_and_authority_closed() -> None:
    contract = build_contract(registry())
    assert contract["metrics"]["python_test_files_written"] == 0
    assert contract["metrics"]["generated_specs_runnable_now"] == 0
    assert contract["metrics"]["converter_code_written"] is False
    assert contract["metrics"]["checkpoint_open_authorized"] is False
    assert contract["metrics"]["packed_decode_authorized"] is False
    assert contract["metrics"]["model_execution_authorized_now"] is False
    assert contract["metrics"]["training_authorized"] is False
    assert all(value is False for value in contract["authority"].values())
