from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9098_trainer_runtime_assertion_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9097) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9098_adds_runtime_assertion_graph_controls() -> None:
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
    assert "contract:trainer_command_surface_static_v1" in node_ids


def test_stage9098_keeps_runtime_and_trainer_invocation_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["runtime_assertions_executed_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["model_forward_attempted"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert not any(card["authority"].values())


def test_stage9098_validation_rejects_open_runtime_trainer_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []
    runtime_assertions = build_card(registry())
    runtime_assertions.pop("graph")
    runtime_assertions["metrics"]["runtime_assertions_executed_now"] = True
    assert "runtime_assertions_executed_now" in validate_card(runtime_assertions, registry())
    trainer = build_card(registry())
    trainer.pop("graph")
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(trainer, registry())
    model_rows = build_card(registry())
    model_rows.pop("graph")
    model_rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(model_rows, registry())
    authority = build_card(registry())
    authority.pop("graph")
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
