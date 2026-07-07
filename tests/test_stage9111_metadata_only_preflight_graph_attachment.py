from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from scripts.build_stage9111_metadata_only_preflight_graph_attachment import (  # noqa: E402
    AUTHORITY_CLOSED,
    NEW_EDGES,
    NEW_NODES,
    build_card,
    validate_card,
)


def registry(latest: int = 9110) -> dict[str, object]:
    return {"metrics": {"latest_stage": latest, "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}


def test_stage9111_adds_metadata_only_preflight_graph_controls() -> None:
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
    assert "contract:trainer_execution_authorization_review_v1" in node_ids


def test_stage9111_keeps_metadata_preflight_non_executing() -> None:
    card = build_card(registry())
    metrics = card["metrics"]

    assert metrics["arxiv_access_performed"] is False
    assert metrics["arxiv_stat_performed"] is False
    assert metrics["dataset_rows_loaded"] is False
    assert metrics["dataset_parquet_groups_read"] is False
    assert metrics["repository_source_bodies_loaded"] is False
    assert metrics["arxiv_write_authorized"] is False
    assert metrics["data_mining_authorized"] is False
    assert metrics["route_cards_materialized_now"] is False
    assert metrics["route_to_loss_translation_ready_now"] is False
    assert metrics["trainer_executed_now"] is False
    assert metrics["contract_only_invoked_now"] is False
    assert metrics["model_forward_attempted"] is False
    assert metrics["training_authorized"] is False
    assert metrics["decoder_ce_authorized"] is False
    assert metrics["denoise_ce_authorized"] is False
    assert metrics["runtime_authorized_flag"] is False
    assert metrics["network_upload_performed"] is False
    assert metrics["cleanup_authorized_now"] is False
    assert not any(card["authority"].values())


def test_stage9111_validation_rejects_access_execution_authority_or_bad_frontier() -> None:
    card = build_card(registry())
    no_graph = dict(card)
    no_graph.pop("graph")
    assert validate_card(no_graph, registry()) == []

    arxiv = build_card(registry())
    arxiv.pop("graph")
    arxiv["metrics"]["arxiv_access_performed"] = True
    assert "arxiv_access_performed" in validate_card(arxiv, registry())

    rows = build_card(registry())
    rows.pop("graph")
    rows["metrics"]["dataset_rows_loaded"] = True
    assert "dataset_rows_loaded" in validate_card(rows, registry())

    trainer = build_card(registry())
    trainer.pop("graph")
    trainer["metrics"]["trainer_executed_now"] = True
    assert "trainer_executed_now" in validate_card(trainer, registry())

    cleanup = build_card(registry())
    cleanup.pop("graph")
    cleanup["metrics"]["cleanup_authorized_now"] = True
    assert "cleanup_authorized_now" in validate_card(cleanup, registry())

    authority = build_card(registry())
    authority.pop("graph")
    authority["authority"]["model_execution_authorized_next"] = True
    assert "authority_open" in validate_card(authority, registry())

    assert "unexpected_registry_frontier:9999" in validate_card(no_graph, registry(latest=9999))
