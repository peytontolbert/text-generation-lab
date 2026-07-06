from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9090_route_to_trainer_loss_translation_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9089) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9090_adds_route_to_loss_graph_controls() -> None:
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
    assert "contract:trainer_dry_run_input_completeness_v1" in node_ids


def test_stage9090_keeps_translation_and_training_closed() -> None:
    card = build_card(registry())
    metrics = card["metrics"]
    assert metrics["translation_ready_now"] is False
    assert metrics["model_input_rows_now"] == 0
    assert metrics["candidate_rows_materialized"] == 0
    assert metrics["trainer_dry_run_ready_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert not any(card["authority"].values())


def test_stage9090_validation_rejects_open_translation_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []
    bad = build_card(registry())
    bad.pop("graph")
    bad["metrics"]["translation_ready_now"] = True
    assert "translation_ready_now" in validate_card(bad, registry())
    bad_rows = build_card(registry())
    bad_rows.pop("graph")
    bad_rows["metrics"]["model_input_rows_now"] = 1
    assert "model_input_rows_now" in validate_card(bad_rows, registry())
    bad_authority = build_card(registry())
    bad_authority.pop("graph")
    bad_authority["authority"]["decoder_ce_training_authorized_next"] = True
    assert "authority_open" in validate_card(bad_authority, registry())
    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
