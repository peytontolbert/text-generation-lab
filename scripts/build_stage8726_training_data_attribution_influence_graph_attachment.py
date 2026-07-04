#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8726
NAME = "stage8726_training_data_attribution_influence_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8724_dataset_cartography_active_learning_graph_attachment/central_research_graph_with_dataset_cartography_active_learning.json"
SOURCE = ROOT / "runs/summaries/stage8725_training_data_attribution_influence_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "TRAINING_DATA_ATTRIBUTION_INFLUENCE_GRAPH_ATTACHMENT_STAGE8726.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def add_node(nodes: dict[str, dict[str, Any]], node: dict[str, Any]) -> bool:
    node_id = node["id"]
    if node_id in nodes:
        nodes[node_id].update(node)
        return False
    nodes[node_id] = node
    return True


def add_edge(edges: list[dict[str, Any]], src: str, relation: str, dst: str) -> None:
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": NAME}
    if edge not in edges:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    module = "support_module:training_data_attribution_influence"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "training_data_attribution_influence", "status": "ready_partial_deterministic_attribution", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    metrics = [
        "attribution_metric:helpful_neighbor",
        "attribution_metric:harmful_conflicting",
        "attribution_metric:missing_neighborhood",
        "attribution_metric:token_overlap",
        "attribution_metric:tag_overlap",
    ]
    for metric in metrics:
        added_nodes += int(add_node(nodes, {"id": metric, "kind": "attribution_metric", "node_type": "attribution_metric", "status": "ready_non_executing", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "emits_metric", metric)
    gates = [
        "gate:missing_neighborhood_requires_data_generation",
        "gate:harmful_conflict_requires_review",
        "gate:helpful_neighbors_required_before_scaleup",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "requires_metric_source", module)
    for upstream in ["support_module:dataset_cartography_active_learning", "support_module:cluster_slice_near_duplicate_detector", "support_module:cross_encoder_reranker_calibration"]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["support_module:curriculum_compiler", "support_module:dataset_patch_generator", "objective:source_backed_scaleup"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "guides_dataset_patch_for", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_training_data_attribution_influence.json"
    nodes_path = OUT_DIR / "central_research_graph_with_training_data_attribution_influence_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_training_data_attribution_influence_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": STAGE, "name": NAME, "stage_name": NAME, "passed": bool(source.get("passed")), "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "metrics_attached": len(metrics), "gates_attached": len(gates), "added_nodes": added_nodes}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))}, "decision": "Attached training-data attribution/influence to central graph; failure-to-data repair can now distinguish helpful, harmful, and missing neighborhoods without model execution.", "next_best_step": "Recover fusion_logits_forward_pass_contract.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "training_data_attribution_influence_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8726 Training Data Attribution Influence Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached deterministic attribution/influence metrics and gates to the central graph.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
