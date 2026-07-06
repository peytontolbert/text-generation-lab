from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9074_trainer_docs_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9073) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9074_adds_trainer_doc_nodes_and_edges() -> None:
    card = build_card(registry())
    graph = card["graph"]
    node_ids = {node["id"] for node in graph["nodes"]}
    edges = {
        (edge.get("source"), edge.get("relation"), edge.get("target"))
        for edge in graph["edges"]
        if edge.get("source") and edge.get("relation") and edge.get("target")
    }
    assert {node["id"] for node in NEW_NODES}.issubset(node_ids)
    assert set(NEW_EDGES).issubset(edges)
    assert card["checks"]["new_nodes_present"] is True
    assert card["checks"]["new_edges_present"] is True


def test_stage9074_keeps_execution_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["trainer_invoked"] is False
    assert card["metrics"]["model_forward_attempted"] is False
    assert card["metrics"]["dataset_rows_loaded"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["authority_rows"] == 0
    assert not any(card["authority"].values())


def test_stage9074_validation_rejects_open_authority_or_bad_frontier() -> None:
    card = build_card(registry())
    without_graph = dict(card)
    without_graph.pop("graph")
    assert validate_card(without_graph, registry()) == []
    bad = build_card(registry())
    bad.pop("graph")
    bad["metrics"]["trainer_dry_run_executed_now"] = True
    assert "trainer_dry_run_executed_now" in validate_card(bad, registry())
    bad_authority = build_card(registry())
    bad_authority.pop("graph")
    bad_authority["authority"]["runtime_authorized"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(without_graph, registry(latest=9999))
