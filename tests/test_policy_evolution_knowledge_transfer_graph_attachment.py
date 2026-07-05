from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_stage8898_policy_evolution_knowledge_transfer_graph_attachment import (
    AUTHORITY_CLOSED,
    EVOLUTION_NODES,
    attach_policy_evolution,
)


def base_graph() -> dict:
    return {
        "nodes": [
            {"id": "model_role:100m_transition_kernel"},
            {"id": "training_objective:transition_prediction"},
            {"id": "training_objective:verified_repair_transition"},
            {"id": "compiler_stage:raw_corpus_to_structured_operators"},
            {"id": "paper_modality:research_operator_card"},
            {"id": "external_memory:retrieval_long_tail_facts"},
            {"id": "architecture_layer:verifier_repair"},
            {"id": "support_module:source_inventory_lineage_tracker"},
            {"id": "support_module:structured_dataset_junk_ranker"},
        ],
        "edges": [],
    }


def test_policy_evolution_adds_static_checkpoint_and_training_cycle() -> None:
    graph, metrics = attach_policy_evolution(base_graph())
    ids = {node["id"] for node in graph["nodes"]}
    assert "policy_state:static_checkpoint_policy" in ids
    assert "loop:evolving_verified_training_cycle" in ids
    assert "dataset_object:verified_transition_record" in ids
    assert metrics["missing_existing_support_nodes"] == []
    assert metrics["added_nodes"] == len(EVOLUTION_NODES)


def test_knowledge_transfer_edges_preserve_memory_boundary() -> None:
    graph, _metrics = attach_policy_evolution(base_graph())
    edges = {(edge["source"], edge["relation"], edge["target"]) for edge in graph["edges"]}
    assert ("policy:knowledge_transfer_policy", "uses", "compiler_stage:research_to_transition_compiler") in edges
    assert ("compiler_stage:research_to_transition_compiler", "produces", "dataset_split:research_transfer_records") in edges
    assert ("boundary:do_not_train_what_tools_can_observe", "routes_facts_to", "external_memory:retrieval_long_tail_facts") in edges


def test_added_nodes_keep_authority_closed() -> None:
    graph, _metrics = attach_policy_evolution(base_graph())
    added = [node for node in graph["nodes"] if node.get("recovered_from")]
    assert added
    assert all(node.get("authority") == AUTHORITY_CLOSED for node in added)
