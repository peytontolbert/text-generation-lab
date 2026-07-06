from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.build_stage9039_long_context_relation_graph_readiness import (  # noqa: E402
    AUTHORITY_CLOSED,
    REQUIRED_EDGE_TYPES,
    build_audit,
    validate_audit,
)


def registry() -> dict[str, object]:
    return {"metrics": {"authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9039_indexes_relation_graph_extension_files() -> None:
    card = build_audit(registry())
    assert card["metrics"]["missing_files"] == 0
    assert "scripts/long_context_relation_graph_builder.py" in card["required_files"]
    assert "scripts/build_stage8800_long_context_transition_dataset.py" in card["required_files"]


def test_stage9039_records_expected_edge_types() -> None:
    card = build_audit(registry())
    assert card["metrics"]["edge_types"] == 5
    assert REQUIRED_EDGE_TYPES == [
        "chunk_mentions_entity",
        "entity_mentioned_by_chunk",
        "entity_co_mention",
        "adjacent_chunk",
        "same_source_chunk",
    ]
    assert validate_audit(card) == []


def test_stage9039_keeps_corpus_scans_and_training_closed() -> None:
    card = build_audit(registry())
    assert card["metrics"]["relation_graph_readiness_only"] is True
    assert card["metrics"]["relation_graph_builder_executed_on_corpus_now"] is False
    assert card["metrics"]["arxiv_scan_authorized_now"] is False
    assert card["metrics"]["repository_library_scan_authorized_now"] is False
    assert card["metrics"]["data_mining_authorized"] is False
    assert card["metrics"]["training_authorized"] is False
    assert all(value is False for value in card["authority"].values())


def test_stage9039_validation_rejects_open_authority_or_corpus_execution() -> None:
    opened = build_audit(registry())
    opened["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_audit(opened)
    unsafe = build_audit(registry())
    unsafe["metrics"]["relation_graph_builder_executed_on_corpus_now"] = True
    assert "relation_graph_builder_executed_on_corpus_now" in validate_audit(unsafe)
