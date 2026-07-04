#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8713_mixed_precision_runtime_contract_graph_attachment/central_research_graph_with_mixed_precision_runtime_contract.json"
SOURCE = ROOT / "runs/summaries/stage8714_repo_graph_encoder_readiness.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8715_repo_graph_encoder_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8715_repo_graph_encoder_graph_attachment.json"
DOC = ROOT / "docs/REPO_GRAPH_ENCODER_GRAPH_ATTACHMENT_STAGE8715.md"

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
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": "stage8715_repo_graph_encoder_graph_attachment"}
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
    module = "support_module:graph_neural_repo_encoder"
    added_nodes = 0
    added_nodes += int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "graph_neural_repo_encoder", "status": "ready_partial_deterministic_message_passing_training_closed", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    metrics = [
        "graph_metric:endpoint_resolution",
        "graph_metric:label_coded_id_block",
        "graph_metric:node_embedding_hash",
        "graph_metric:graph_embedding_hash",
        "graph_metric:relation_message_passing",
    ]
    for metric in metrics:
        added_nodes += int(add_node(nodes, {"id": metric, "kind": "graph_metric", "node_type": "graph_metric", "status": "ready_non_executing", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "emits_metric", metric)
    for objective in ["objective:symbol_binding", "objective:edit_localization", "objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_arguments"]:
        add_node(nodes, {"id": objective, "kind": "objective", "node_type": "objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "provides_graph_features_for", objective)
    for gate in ["gate:graph_endpoint_resolution_required", "gate:label_coded_graph_ids_blocked", "gate:same_degree_counterbalance_required"]:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "requires_metric_source", module)
    out = {"version": "stage8715_repo_graph_encoder_graph_attachment", "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_repo_graph_encoder.json"
    nodes_path = OUT_DIR / "central_research_graph_with_repo_graph_encoder_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_repo_graph_encoder_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": 8715,
        "name": "stage8715_repo_graph_encoder_graph_attachment",
        "stage_name": "stage8715_repo_graph_encoder_graph_attachment",
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {"authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "metrics_attached": len(metrics), "gates_attached": 3, **AUTHORITY_CLOSED},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached repo graph encoder as deterministic graph-feature scaffold; learned GNN/model training remains closed.",
        "next_best_step": "Recover rubric judge calibration or operator/codelength interfaces; keep mining/training closed until support modules are complete.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "repo_graph_encoder_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8715 Repo Graph Encoder Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Graph nodes: `{len(out['nodes'])}`",
        f"Graph edges: `{len(out['edges'])}`",
        "",
        "Attached deterministic repo graph encoder metrics and gates. Learned GNN training remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
