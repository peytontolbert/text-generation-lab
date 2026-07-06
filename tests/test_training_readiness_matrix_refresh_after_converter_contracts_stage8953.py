from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8953_training_readiness_matrix_refresh_after_converter_contracts import (  # noqa: E402
    AUTHORITY_CLOSED,
    FORBIDDEN_NEXT_OPERATIONS,
    REQUIRED_PASSED_SOURCE_STAGES,
    build_matrix,
    validate_matrix,
)


def registry(latest: int = 8952) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage8953_records_converter_contract_chain_without_training_authority() -> None:
    matrix = build_matrix(registry())
    assert matrix["metrics"]["required_passed_source_stages"] == len(REQUIRED_PASSED_SOURCE_STAGES)
    assert matrix["metrics"]["required_passed_source_stages_passed"] == len(REQUIRED_PASSED_SOURCE_STAGES)
    assert matrix["metrics"]["converter_contract_chain_complete"] is True
    assert matrix["metrics"]["training_ready_components"] == 0
    assert matrix["metrics"]["training_authorized"] is False


def test_stage8953_preserves_stage8949_as_superseded_failure() -> None:
    matrix = build_matrix(registry())
    historical = matrix["historical_superseded_failures"]["8949"]
    assert historical["preserved"] is True
    assert historical["passed"] is False
    assert historical["superseded_by"] == 8951
    assert matrix["checks"]["stage8949_preserved_as_superseded_failure"] is True


def test_stage8953_forbids_converter_checkpoint_model_mining_and_training_next_ops() -> None:
    matrix = build_matrix(registry())
    for operation in [
        "run_converter",
        "open_checkpoint",
        "read_tensor_bytes",
        "instantiate_model",
        "run_training_step",
        "mine_new_data",
        "run_bounded_decoder_ce_probe",
    ]:
        assert operation in FORBIDDEN_NEXT_OPERATIONS
    assert matrix["metrics"]["converter_implementation_complete"] is False
    assert matrix["metrics"]["checkpoint_materialization_authorized"] is False
    assert matrix["metrics"]["model_execution_authorized_now"] is False
    assert matrix["metrics"]["data_mining_authorized"] is False


def test_stage8953_validation_rejects_open_authority_or_bad_frontier() -> None:
    matrix = build_matrix(registry())
    assert validate_matrix(matrix, registry()) == []
    bad = build_matrix(registry())
    bad["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad, registry())
    bad_training = build_matrix(registry())
    bad_training["metrics"]["training_authorized"] = True
    assert "training_authorized" in validate_matrix(bad_training, registry())
    assert "unexpected_registry_frontier:9999" in validate_matrix(matrix, registry(latest=9999))
