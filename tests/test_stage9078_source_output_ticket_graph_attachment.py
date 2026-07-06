from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9078_source_output_ticket_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9077) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9078_adds_source_output_ticket_graph_controls() -> None:
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
    assert "gate:never_delete_arxiv" in node_ids


def test_stage9078_keeps_ticket_and_access_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["ticket_instantiated_now"] is False
    assert card["metrics"]["source_metadata_read_now"] is False
    assert card["metrics"]["repository_source_bodies_read_now"] is False
    assert card["metrics"]["route_cards_materialized_now"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert not any(card["authority"].values())


def test_stage9078_validation_rejects_open_access_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []
    bad = build_card(registry())
    bad.pop("graph")
    bad["metrics"]["route_cards_materialized_now"] = True
    assert "route_cards_materialized_now" in validate_card(bad, registry())
    bad_authority = build_card(registry())
    bad_authority.pop("graph")
    bad_authority["authority"]["source_emission_authorized"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
