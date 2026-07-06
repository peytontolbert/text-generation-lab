from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9064_training_readiness_refresh_after_long_context_controls import (  # noqa: E402
    AUTHORITY_CLOSED,
    TRAINING_BLOCKERS,
    build_matrix,
    validate_matrix,
)


def registry(latest: int = 9063) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9064_records_long_context_training_blockers() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["source_summaries_passed"] == matrix["metrics"]["source_summaries"]
    assert len(TRAINING_BLOCKERS) >= 8
    assert matrix["metrics"]["hard_blockers"] >= 7
    assert matrix["checks"]["compiler_ready_rows_zero"] is True


def test_stage9064_keeps_training_mining_and_losses_closed() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["training_ready"] is False
    assert matrix["metrics"]["data_mining_authorized"] is False
    assert matrix["metrics"]["decoder_ce_authorized"] is False
    assert matrix["metrics"]["denoise_ce_authorized"] is False
    assert matrix["metrics"]["runtime_authorized_flag"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_stage9064_validation_rejects_authority_or_training_reopen() -> None:
    matrix = build_matrix(registry())
    assert validate_matrix(matrix, registry()) == []
    bad = build_matrix(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad, registry())
    bad_train = build_matrix(registry())
    bad_train["metrics"]["training_ready"] = True
    assert "training_ready" in validate_matrix(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(matrix, registry(latest=9999))
