from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9086_trainer_dry_run_input_controls_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9085) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9086_adds_trainer_input_control_graph_nodes() -> None:
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
    assert "contract:route_card_materialization_audit_instance_inactive_v1" in node_ids


def test_stage9086_keeps_trainer_and_route_to_loss_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["trainer_dry_run_executed_now"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["compiler_handoff_ready_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["arxiv_read_authorized_for_compiler"] is False
    assert not any(card["authority"].values())


def test_stage9086_validation_rejects_open_trainer_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []
    bad = build_card(registry())
    bad.pop("graph")
    bad["metrics"]["route_to_loss_translation_ready_now"] = True
    assert "route_to_loss_translation_ready_now" in validate_card(bad, registry())
    bad_rows = build_card(registry())
    bad_rows.pop("graph")
    bad_rows["metrics"]["candidate_rows_materialized"] = 1
    assert "candidate_rows_materialized" in validate_card(bad_rows, registry())
    bad_authority = build_card(registry())
    bad_authority.pop("graph")
    bad_authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
