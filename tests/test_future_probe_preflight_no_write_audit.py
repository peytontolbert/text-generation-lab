from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8923_future_probe_preflight_no_write_audit import (  # noqa: E402
    AUTHORITY_CLOSED,
    build_preflight,
    negative_mutation_results,
    validate_preflight,
)


def test_preflight_is_read_only_and_reserves_safe_artifacts() -> None:
    preflight = build_preflight(output_root_exists=False)
    metrics = preflight["metrics"]
    assert metrics["output_root_exists"] is False
    assert metrics["required_artifact_names"] >= 15
    assert metrics["required_artifact_names_unique"] is True
    assert metrics["unsafe_required_artifact_names"] == []
    assert metrics["would_create_directories"] is False
    assert metrics["would_write_artifacts"] is False
    assert metrics["would_delete_artifacts"] is False


def test_preflight_rejects_existing_output_root() -> None:
    preflight = build_preflight(output_root_exists=True)
    registry = {"metrics": {"latest_stage": 8922, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}
    source_summary = {"passed": True, "authority": AUTHORITY_CLOSED}
    failures = validate_preflight(preflight, registry, source_summary)
    assert "output_root_fresh" in failures


def test_preflight_keeps_authority_closed() -> None:
    preflight = build_preflight(output_root_exists=False)
    assert all(value is False for value in preflight["authority"].values())
    assert preflight["checks"]["no_model_execution"] is True
    assert preflight["checks"]["no_training"] is True


def test_preflight_rejects_negative_mutations() -> None:
    results = negative_mutation_results(build_preflight(output_root_exists=False))
    assert results
    assert all(result["rejected"] for result in results.values())
