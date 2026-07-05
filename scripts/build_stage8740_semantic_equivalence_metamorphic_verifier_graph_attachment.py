#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8740
NAME = "stage8740_semantic_equivalence_metamorphic_verifier_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8738_structured_data_operation_curriculum_graph_attachment/central_research_graph_with_structured_data_operation_curriculum.json"
SOURCE = ROOT / "runs/summaries/stage8739_semantic_equivalence_metamorphic_verifier_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SEMANTIC_EQUIVALENCE_METAMORPHIC_VERIFIER_GRAPH_ATTACHMENT_STAGE8740.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "denoise_ce_training_authorized_next": False,
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
    module = "support_module:semantic_equivalence_metamorphic_verifier"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "semantic_equivalence_metamorphic_verifier", "status": "ready_partial_no_execution_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    verifier_types = ["semantic_equivalence", "property_contract", "metamorphic_relation", "api_compatibility", "determinism_contract"]
    for typ in verifier_types:
        node_id = f"semantic_verifier:{typ}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "semantic_verifier_type", "node_type": "semantic_verifier_type", "status": "ready_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "supports_verifier_type", node_id)
    gates = [
        "gate:semantic_verifier_never_executes_runtime",
        "gate:semantic_verifier_never_authorizes_scoring",
        "gate:api_compatibility_required_for_public_surface",
        "gate:determinism_required_for_repeatable_patch",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for upstream in ["support_module:runtime_verifier_loop_contract", "support_module:operator_codelength_interface", "support_module:structured_data_operation_curriculum"]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_ce", "support_module:curriculum_compiler"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "verifies_contract_for", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_semantic_equivalence_metamorphic_verifier.json"
    nodes_path = OUT_DIR / "central_research_graph_with_semantic_equivalence_metamorphic_verifier_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_semantic_equivalence_metamorphic_verifier_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": STAGE, "name": NAME, "stage_name": NAME, "passed": bool(source.get("passed")), "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "verifier_types_attached": len(verifier_types), "gates_attached": len(gates), "added_nodes": added_nodes}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))}, "decision": "Attached semantic equivalence/metamorphic verifier to central graph. Verification remains static contract checking only.", "next_best_step": "Refresh forgotten-module queue status and decide whether support-module recovery is complete enough for the next non-training audit.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "semantic_equivalence_metamorphic_verifier_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8740 Semantic Equivalence Metamorphic Verifier Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached semantic equivalence, property, metamorphic, API compatibility, and determinism verifier contracts to the central graph.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
