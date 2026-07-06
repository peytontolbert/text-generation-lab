from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8924_training_readiness_blocker_matrix import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_matrix,
    validate_matrix,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8923, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_matrix_records_ready_components_and_blockers() -> None:
    matrix = build_matrix(registry())
    assert matrix["checks"]["blockers_present"] is True
    assert matrix["checks"]["ready_components_present"] is True
    blocker_names = {row["blocker"] for row in matrix["blockers"]}
    assert "tokenizer_vocab_mismatch" in blocker_names
    assert "packed_bitnet_decode_blocked" in blocker_names
    assert "checkpoint_materialization_noop_only" in blocker_names


def test_matrix_keeps_training_and_execution_blocked() -> None:
    matrix = build_matrix(registry())
    assert matrix["checks"]["training_remains_blocked"] is True
    assert matrix["checks"]["model_execution_remains_blocked"] is True
    assert matrix["checks"]["decoder_ce_remains_blocked"] is True
    assert matrix["checks"]["runtime_remains_blocked"] is True
    assert matrix["metrics"]["training_authorized"] is False
    assert matrix["metrics"]["model_execution_authorized_now"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_matrix_sources_are_present_and_passed() -> None:
    matrix = build_matrix(registry())
    assert matrix["checks"]["all_source_summaries_present"] is True
    assert matrix["checks"]["all_source_summaries_passed"] is True
    assert matrix["metrics"]["source_summaries_present"] == matrix["metrics"]["source_stages"]


def test_validation_rejects_open_authority_or_bad_frontier() -> None:
    assert validate_matrix(build_matrix(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["authority_counts"]["runtime_authorized"] = 1  # type: ignore[index]
    assert "authority_counts_zero" in validate_matrix(build_matrix(bad_registry), bad_registry)
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_matrix(build_matrix(registry()), bad_registry)
