from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8938_checkpoint_materialization_precondition_matrix import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_matrix,
    validate_matrix,
)


def registry(latest: int = 8937) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8938_records_resolved_and_blocked_preconditions() -> None:
    matrix = build_matrix(registry())
    rows = {row["precondition"]: row for row in matrix["preconditions"]}
    assert rows["tokenizer_hash_lock"]["status"].startswith("resolved")
    assert rows["bitnet_layout_decoder_contract"]["status"].startswith("blocked")
    assert rows["control_head_initializer_seed_contract"]["status"].startswith("blocked")
    assert matrix["metrics"]["blocked_preconditions"] >= 5


def test_stage8938_keeps_checkpoint_and_training_authority_closed() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["checkpoint_load_authorized"] is False
    assert matrix["metrics"]["checkpoint_write_authorized"] is False
    assert matrix["metrics"]["training_authorized"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_stage8938_validation_rejects_open_authority_or_bad_frontier() -> None:
    matrix = build_matrix(registry())
    assert validate_matrix(matrix, registry()) == []
    bad_matrix = build_matrix(registry())
    bad_matrix["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad_matrix, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(matrix, registry(latest=9999))
