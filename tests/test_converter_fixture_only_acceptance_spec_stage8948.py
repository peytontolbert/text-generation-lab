from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8948_converter_fixture_only_acceptance_spec import (  # noqa: E402
    ACCEPTANCE_SPEC_ROWS,
    AUTHORITY_CLOSED,
    GLOBAL_FORBIDDEN_OPERATIONS,
    build_spec,
    validate_spec,
)


def registry(latest: int = 8947) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8948_records_fixture_only_acceptance_specs() -> None:
    spec = build_spec(registry())
    assert len(ACCEPTANCE_SPEC_ROWS) >= 5
    assert len(GLOBAL_FORBIDDEN_OPERATIONS) >= 9
    assert spec["metrics"]["real_checkpoint_fixture_rows"] == 0
    assert spec["metrics"]["real_tensor_fixture_rows"] == 0
    assert all(row["fixture_type"].endswith("_only") for row in spec["acceptance_spec_rows"])


def test_stage8948_keeps_converter_checkpoint_and_training_closed() -> None:
    spec = build_spec(registry())
    assert spec["metrics"]["converter_code_written"] is False
    assert spec["metrics"]["converter_execution_authorized"] is False
    assert spec["metrics"]["checkpoint_open_authorized"] is False
    assert spec["metrics"]["checkpoint_write_authorized"] is False
    assert spec["metrics"]["model_execution_authorized_now"] is False
    assert spec["metrics"]["training_authorized"] is False
    assert all(value is False for value in spec["authority"].values())


def test_stage8948_validation_rejects_real_fixture_or_open_authority() -> None:
    spec = build_spec(registry())
    assert validate_spec(spec, registry()) == []
    bad_fixture = build_spec(registry())
    bad_fixture["metrics"]["real_tensor_fixture_rows"] = 1
    assert "real_tensor_fixture_rows" in validate_spec(bad_fixture, registry())
    bad_authority = build_spec(registry())
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_spec(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_spec(spec, registry(latest=9999))
