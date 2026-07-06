from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage8978_duplicate_stage_artifact_preservation import (  # noqa: E402
    ACTIVE_PATHS_THAT_SHOULD_NOT_EXIST,
    AUTHORITY_CLOSED,
    PRESERVED_PATHS,
    validate_card,
)


def registry(latest: int = 8977) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def base_card() -> dict[str, object]:
    return {
        "checks": {"ok": True},
        "authority": dict(AUTHORITY_CLOSED),
        "metrics": {
            "delete_or_cleanup_performed": False,
            "dataset_rows_loaded": False,
            "repository_source_bodies_loaded": False,
            "schema_or_header_read_performed": False,
            "arxiv_write_authorized": False,
            "training_authorized": False,
            "data_mining_authorized": False,
            "model_execution_attempted": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
            "network_upload_performed": False,
        },
    }


def test_stage8978_preserved_paths_are_outside_active_summaries() -> None:
    assert PRESERVED_PATHS
    assert all(path.startswith(("docs/superseded/", "scripts/superseded/", "tests/superseded/", "runs/local/artifacts/superseded_duplicate_stage_artifacts/")) for path in PRESERVED_PATHS)


def test_stage8978_active_paths_are_duplicate_conflict_paths() -> None:
    assert any(path.startswith("runs/summaries/") for path in ACTIVE_PATHS_THAT_SHOULD_NOT_EXIST)
    assert any(path.startswith("scripts/") for path in ACTIVE_PATHS_THAT_SHOULD_NOT_EXIST)


def test_stage8978_validation_rejects_delete_or_training() -> None:
    assert validate_card(base_card(), registry()) == []
    bad = base_card()
    bad["metrics"] = {**bad["metrics"], "delete_or_cleanup_performed": True}
    assert "delete_or_cleanup_performed" in validate_card(bad, registry())
    trained = base_card()
    trained["metrics"] = {**trained["metrics"], "training_authorized": True}
    assert "training_authorized" in validate_card(trained, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(base_card(), registry(9999))
