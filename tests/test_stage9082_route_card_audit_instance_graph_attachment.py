from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9082_route_card_audit_instance_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9081) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9082_adds_route_card_instance_graph_controls() -> None:
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
    assert "contract:source_output_ticket_inactive_v1" in node_ids


def test_stage9082_keeps_instance_and_compiler_closed() -> None:
    card = build_card(registry())
    assert card["metrics"]["instance_instantiated_now"] is False
    assert card["metrics"]["source_output_ticket_instantiated_now"] is False
    assert card["metrics"]["route_cards_materialized_now"] is False
    assert card["metrics"]["candidate_rows_materialized"] == 0
    assert card["metrics"]["compiler_handoff_ready_now"] is False
    assert card["metrics"]["trainer_dry_run_ready_now"] is False
    assert not any(card["authority"].values())


def test_stage9082_validation_rejects_open_instance_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []
    bad = build_card(registry())
    bad.pop("graph")
    bad["metrics"]["compiler_handoff_ready_now"] = True
    assert "compiler_handoff_ready_now" in validate_card(bad, registry())
    bad_authority = build_card(registry())
    bad_authority.pop("graph")
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
