from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9106_execution_authorization_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9105) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9106_adds_execution_authorization_graph_controls() -> None:
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
    assert "contract:trainer_contract_only_artifact_schema_v1" in node_ids


def test_stage9106_keeps_execution_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]
    assert metrics["same_stage_execution_authorized"] is False
    assert metrics["next_stage_execution_authorized"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["runtime_assertions_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9106_validation_rejects_open_execution_cleanup_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []
    same_stage = build_card(registry())
    same_stage.pop("graph")
    same_stage["metrics"]["same_stage_execution_authorized"] = True
    assert "same_stage_execution_authorized" in validate_card(same_stage, registry())
    next_stage = build_card(registry())
    next_stage.pop("graph")
    next_stage["metrics"]["next_stage_execution_authorized"] = True
    assert "next_stage_execution_authorized" in validate_card(next_stage, registry())
    cleanup = build_card(registry())
    cleanup.pop("graph")
    cleanup["metrics"]["cleanup_authorized_now"] = True
    assert "cleanup_authorized_now" in validate_card(cleanup, registry())
    rows = build_card(registry())
    rows.pop("graph")
    rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(rows, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
