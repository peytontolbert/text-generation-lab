#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8724
NAME = "stage8724_dataset_cartography_active_learning_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8722_cross_encoder_reranker_calibration_graph_attachment/central_research_graph_with_cross_encoder_reranker_calibration.json"
SOURCE = ROOT / "runs/summaries/stage8723_dataset_cartography_active_learning_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "DATASET_CARTOGRAPHY_ACTIVE_LEARNING_GRAPH_ATTACHMENT_STAGE8724.md"

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
    module = "support_module:dataset_cartography_active_learning"
    added_nodes = int(add_node(nodes, {
        "id": module,
        "kind": "support_module",
        "node_type": "support_module",
        "name": "dataset_cartography_active_learning",
        "status": "ready_partial_deterministic_sampler",
        "summary": str(SOURCE.relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    metrics = [
        "cartography_metric:confidence_mean",
        "cartography_metric:confidence_variability",
        "cartography_metric:loss_mean",
        "cartography_metric:forgetting_events",
        "cartography_metric:label_review_rows",
        "cartography_metric:neighbor_generation_rows",
    ]
    for metric in metrics:
        added_nodes += int(add_node(nodes, {"id": metric, "kind": "cartography_metric", "node_type": "cartography_metric", "status": "ready_non_executing", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "emits_metric", metric)
    gates = [
        "gate:label_review_before_scaleup",
        "gate:easy_redundant_rows_downsampled",
        "gate:ambiguous_rows_keep_counterfactual_neighbors",
        "gate:hard_rows_require_neighbor_generation",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "requires_metric_source", module)
    for upstream in ["support_module:training_telemetry_metrics", "support_module:cluster_slice_near_duplicate_detector", "support_module:dataset_junk_ood_ranker_v1"]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["support_module:curriculum_compiler", "support_module:forgotten_vital_module_gap_audit", "objective:source_backed_scaleup"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "selects_rows_for", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_dataset_cartography_active_learning.json"
    nodes_path = OUT_DIR / "central_research_graph_with_dataset_cartography_active_learning_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_dataset_cartography_active_learning_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "graph_nodes": len(out["nodes"]),
            "graph_edges": len(out["edges"]),
            "metrics_attached": len(metrics),
            "gates_attached": len(gates),
            "added_nodes": added_nodes,
        },
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": "Attached dataset cartography/active-learning sampler to central graph; scale-up remains gated by label review and neighbor generation.",
        "next_best_step": "Recover training_data_attribution_influence.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "dataset_cartography_active_learning_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8724 Dataset Cartography Active Learning Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached dataset cartography metrics and active-learning gates to the central graph.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
