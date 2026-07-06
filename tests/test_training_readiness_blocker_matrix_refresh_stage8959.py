from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8959_training_readiness_blocker_matrix_refresh import (  # noqa: E402
    AUTHORITY_CLOSED,
    READY_NO_EXECUTION_COMPONENTS,
    TRAINING_BLOCKERS,
    build_matrix,
    validate_matrix,
)


def registry(latest: int = 8958) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8959_records_recovered_no_execution_components_and_blockers() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["source_summaries_passed"] == matrix["metrics"]["source_summaries"]
    assert len(READY_NO_EXECUTION_COMPONENTS) >= 16
    assert len(TRAINING_BLOCKERS) >= 8
    assert matrix["metrics"]["ready_no_execution_components"] >= 16
    assert matrix["metrics"]["hard_blockers"] >= 7


def test_stage8959_keeps_training_mining_execution_and_arxiv_closed() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["training_ready"] is False
    assert matrix["metrics"]["actual_execution_authorized_next"] is False
    assert matrix["metrics"]["data_mining_authorized"] is False
    assert matrix["metrics"]["training_authorized"] is False
    assert matrix["metrics"]["arxiv_read_authorized_for_compiler"] is False
    assert matrix["metrics"]["arxiv_write_authorized"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_stage8959_validation_rejects_authority_or_training_reopen() -> None:
    matrix = build_matrix(registry())
    assert validate_matrix(matrix, registry()) == []
    bad = build_matrix(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad, registry())
    bad_train = build_matrix(registry())
    bad_train["metrics"]["training_ready"] = True
    assert "training_ready" in validate_matrix(bad_train, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(matrix, registry(latest=9999))
