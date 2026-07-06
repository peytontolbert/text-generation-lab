from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8943_checkpoint_precondition_matrix_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_matrix,
    validate_matrix,
)


def registry(latest: int = 8942) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8943_matrix_has_one_remaining_bitnet_semantics_blocker() -> None:
    matrix = build_matrix(registry())
    blocked = [row for row in matrix["preconditions"] if row["status"].startswith("blocked")]
    assert matrix["metrics"]["resolved_preconditions"] == 9
    assert matrix["metrics"]["blocked_preconditions"] == 1
    assert blocked[0]["precondition"] == "bitnet_layout_decoder_contract"


def test_stage8943_keeps_checkpoint_decode_and_training_closed() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["checkpoint_load_authorized"] is False
    assert matrix["metrics"]["checkpoint_write_authorized"] is False
    assert matrix["metrics"]["decode_packed_bitnet_authorized"] is False
    assert matrix["metrics"]["training_authorized"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_stage8943_validation_rejects_bad_frontier_or_open_authority() -> None:
    matrix = build_matrix(registry())
    assert validate_matrix(matrix, registry()) == []
    bad_matrix = build_matrix(registry())
    bad_matrix["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad_matrix, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(matrix, registry(latest=9999))
