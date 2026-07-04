#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8717_rubric_judge_calibrator_graph_attachment/central_research_graph_with_rubric_judge_calibrator.json"
SOURCE = ROOT / "runs/summaries/stage8718_operator_codelength_interface_readiness.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8719_operator_codelength_interface_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8719_operator_codelength_interface_graph_attachment.json"
DOC = ROOT / "docs/OPERATOR_CODELENGTH_INTERFACE_GRAPH_ATTACHMENT_STAGE8719.md"

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
    edge = {"src": src, "edge_type": relation, "dst": dst, "source": src, "relation": relation, "target": dst, "evidence_source": "stage8719_operator_codelength_interface_graph_attachment"}
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
    module = "support_module:operator_codelength_interface"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "operator_codelength_interface", "status": "ready_non_executing", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    metrics = ["metric:uniform_bits", "metric:model_nll_bits", "metric:compression_gain_bits", "metric:regret_vs_perfect_bits", "metric:bits_per_row"]
    for metric in metrics:
        added_nodes += int(add_node(nodes, {"id": metric, "kind": "codelength_metric", "node_type": "codelength_metric", "status": "ready_non_executing", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "emits_metric", metric)
    for gate in ["gate:codelength_required_for_choice_probe", "gate:accuracy_alone_insufficient", "gate:operator_contract_required"]:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "requires_metric_source", module)
    for downstream in ["objective:intent_to_build_strategy", "objective:symbol_binding", "objective:patch_operator", "objective:bounded_decoder_ce", "support_module:curriculum_compiler"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "measures_choice_surface_for", downstream)
    out = {"version": "stage8719_operator_codelength_interface_graph_attachment", "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_operator_codelength_interface.json"
    nodes_path = OUT_DIR / "central_research_graph_with_operator_codelength_interface_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_operator_codelength_interface_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": 8719, "name": "stage8719_operator_codelength_interface_graph_attachment", "stage_name": "stage8719_operator_codelength_interface_graph_attachment", "passed": bool(source.get("passed")), "authority": AUTHORITY_CLOSED, "metrics": {"authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "metrics_attached": len(metrics), "gates_attached": 3, **AUTHORITY_CLOSED}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))}, "decision": "Attached operator inventory/codelength interface to central graph; accuracy-only probe promotion remains blocked.", "next_best_step": "Run module gap review and only then decide whether data mining can resume under closed-authority manifests.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "operator_codelength_interface_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8719 Operator/Codelength Interface Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached codelength metrics and operator contract gates. Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
