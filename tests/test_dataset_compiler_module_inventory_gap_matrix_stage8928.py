from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8928_dataset_compiler_module_inventory_gap_matrix import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_matrix,
    validate_matrix,
)


def registry() -> dict[str, object]:
    return {"metrics": {"latest_stage": 8927, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_inventory_finds_core_compiler_modules() -> None:
    matrix = build_matrix(registry())
    areas = {row["area"] for row in matrix["modules"]}
    assert "curriculum_compiler" in areas
    assert "unified_junk_ood_ranker" in areas
    assert "semantic_equivalence" in areas
    assert "training_influence" in areas
    assert "repo_graph_encoder" in areas
    assert matrix["checks"]["all_required_scripts_present"] is True


def test_inventory_records_expected_gaps() -> None:
    matrix = build_matrix(registry())
    gaps = {row["gap"] for row in matrix["known_gaps"]}
    assert "single_orchestrated_compiler_api" in gaps
    assert "source_extractors_need_tests" in gaps
    assert "structured_junk_ranker_test_gap" in gaps
    assert "counterfactual_obligation_test_gap" in gaps


def test_inventory_keeps_mining_and_training_blocked() -> None:
    matrix = build_matrix(registry())
    assert matrix["checks"]["training_remains_blocked"] is True
    assert matrix["checks"]["data_mining_remains_blocked"] is True
    assert matrix["checks"]["runtime_remains_blocked"] is True
    assert matrix["metrics"]["training_authorized"] is False
    assert matrix["metrics"]["data_mining_authorized"] is False
    assert all(value is False for value in matrix["authority"].values())


def test_validation_rejects_bad_frontier_or_authority() -> None:
    assert validate_matrix(build_matrix(registry()), registry()) == []
    bad_registry = registry()
    bad_registry["metrics"]["latest_stage"] = 9999  # type: ignore[index]
    assert "unexpected_registry_frontier:9999" in validate_matrix(build_matrix(registry()), bad_registry)
    bad_matrix = build_matrix(registry())
    bad_matrix["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_matrix(bad_matrix, registry())
