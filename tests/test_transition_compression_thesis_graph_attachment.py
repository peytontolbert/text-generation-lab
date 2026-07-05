from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8897_transition_compression_thesis_graph_attachment import (
    AUTHORITY_CLOSED,
    THESIS_NODES,
    attach_transition_thesis,
)


def base_graph() -> dict:
    return {
        "nodes": [
            {"id": "architecture_layer:repo_state_graph_v1"},
            {"id": "architecture_layer:verifier_repair"},
            {"id": "support_module:source_inventory_lineage_tracker"},
            {"id": "support_module:structured_dataset_junk_ranker"},
        ],
        "edges": [],
    }


def test_transition_thesis_adds_kernel_and_memory_boundary_nodes() -> None:
    graph, metrics = attach_transition_thesis(base_graph())
    ids = {node["id"] for node in graph["nodes"]}
    assert "thesis:transition_compression_not_world_memory" in ids
    assert "model_role:100m_transition_kernel" in ids
    assert "external_memory:retrieval_long_tail_facts" in ids
    assert "capacity_contract:parametric_memory_boundary" in ids
    assert metrics["missing_existing_support_nodes"] == []
    assert metrics["added_nodes"] == len(THESIS_NODES)


def test_transition_thesis_edges_capture_division_of_labor() -> None:
    graph, _metrics = attach_transition_thesis(base_graph())
    edges = {(edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]}
    assert ("capacity_contract:parametric_memory_boundary", "routes_long_tail_to", "external_memory:retrieval_long_tail_facts") in edges
    assert ("training_objective:transition_prediction", "trains", "model_role:100m_transition_kernel") in edges
    assert ("paper_modality:research_operator_card", "feeds", "compiler_stage:raw_corpus_to_structured_operators") in edges


def test_transition_thesis_keeps_all_new_nodes_authority_closed() -> None:
    graph, _metrics = attach_transition_thesis(base_graph())
    new_ids = {node["id"] for node in THESIS_NODES}
    for node in graph["nodes"]:
        if node.get("id") in new_ids:
            assert node["authority"] == AUTHORITY_CLOSED


def test_transition_thesis_reports_missing_support_nodes() -> None:
    _graph, metrics = attach_transition_thesis({"nodes": [], "edges": []})
    assert set(metrics["missing_existing_support_nodes"]) == {
        "architecture_layer:repo_state_graph_v1",
        "architecture_layer:verifier_repair",
        "support_module:source_inventory_lineage_tracker",
        "support_module:structured_dataset_junk_ranker",
    }
