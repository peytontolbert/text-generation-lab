from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8945_checkpoint_precondition_matrix_all_contracts_recovered import (  # noqa: E402
    AUTHORITY_CLOSED,
    IMPLEMENTATION_BLOCKERS,
    build_matrix,
    validate_matrix,
)


def registry(latest: int = 8944) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8945_all_precondition_contracts_recovered_but_implementation_blocked() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["recovered_precondition_contracts"] == matrix["metrics"]["preconditions"]
    assert matrix["metrics"]["blocked_precondition_contracts"] == 0
    assert len(IMPLEMENTATION_BLOCKERS) >= 6
    assert "converter_implementation_not_written" in IMPLEMENTATION_BLOCKERS


def test_stage8945_keeps_real_decode_checkpoint_and_training_closed() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["real_packed_decode_authorized"] is False
    assert matrix["metrics"]["checkpoint_load_authorized"] is False
    assert matrix["metrics"]["checkpoint_write_authorized"] is False
    assert matrix["metrics"]["training_authorized"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_stage8945_validation_rejects_bad_frontier_or_open_authority() -> None:
    matrix = build_matrix(registry())
    assert validate_matrix(matrix, registry()) == []
    bad_matrix = build_matrix(registry())
    bad_matrix["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad_matrix, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(matrix, registry(latest=9999))
