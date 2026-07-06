from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9037_long_context_transition_pipeline_readiness import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_PIPELINE_STEPS,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9037_indexes_recovered_pipeline_files() -> None:
    card = build_audit(registry())
    assert card["metrics"]["required_files"] >= 8
    assert card["metrics"]["missing_files"] == 0
    assert "scripts/long_context_chunk_catalog.py" in card["required_files"]
    assert "scripts/long_context_shortcut_audit.py" in card["required_files"]
    assert "tests/test_long_context_transition_pipeline.py" in card["required_files"]


def test_stage9037_records_pipeline_steps() -> None:
    card = build_audit(registry())
    assert card["metrics"]["pipeline_steps"] == 5
    assert REQUIRED_PIPELINE_STEPS == [
        "chunk_catalog",
        "entity_linking",
        "latent_transition_program_builder",
        "long_context_example_renderer",
        "shortcut_quality_audit",
    ]
    assert validate_audit(card) == []


def test_stage9037_keeps_data_scans_and_training_closed() -> None:
    card = build_audit(registry())
    assert card["metrics"]["readiness_audit_only"] is True
    assert card["metrics"]["arxiv_scan_attempted"] is False
    assert card["metrics"]["repository_library_scan_attempted"] is False
    assert card["metrics"]["long_context_dataset_materialized_now"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert card["metrics"]["decoder_ce_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9037_validation_rejects_open_authority_or_materialization() -> None:
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["long_context_dataset_materialized_now"] = True
    assert "long_context_dataset_materialized_now" in validate_audit(unsafe)
