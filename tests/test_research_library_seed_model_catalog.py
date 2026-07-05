from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8904_research_library_seed_model_catalog import (
    AUTHORITY_CLOSED,
    CANDIDATES,
    DIRECT_CORE_SEED,
    build_catalog,
    validate_catalog,
)


def test_catalog_has_single_direct_core_seed() -> None:
    catalog = build_catalog()
    assert DIRECT_CORE_SEED == ["local_agentkernel_lite_100m_bitnet_v11"]
    primary = [item for item in catalog["candidates"] if item["role"] == "primary_seed_candidate"]
    assert [item["name"] for item in primary] == DIRECT_CORE_SEED


def test_catalog_includes_required_side_teachers() -> None:
    names = {item["name"] for item in CANDIDATES}
    for name in [
        "PeytonT/repo-state-grounding",
        "PeytonT/jepa-repo-state",
        "PeytonT/cross-encoder-reranker",
        "PeytonT/verifier-accept-policy",
        "PeytonT/paper-to-code",
        "local_m1_lite_and_scibert_onnx",
    ]:
        assert name in names


def test_catalog_validation_keeps_authority_closed() -> None:
    registry = {"metrics": {"latest_stage": 8903, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    assert validate_catalog(build_catalog(), registry) == []
    registry["metrics"]["authority_counts"]["model_execution_authorized_next"] = 1
    assert "registry_authority_counts_nonzero" in validate_catalog(build_catalog(), registry)


def test_every_candidate_has_risk_and_use_case() -> None:
    for item in CANDIDATES:
        assert item["use_for"]
        assert item["why"]
        assert item["risk"]
