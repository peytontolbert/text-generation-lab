#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8747
NAME = "stage8747_contamination_leakage_detector_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8744_source_provenance_license_security_filter_graph_attachment/central_research_graph_with_source_provenance_license_security_filter.json"
SOURCE = ROOT / "runs/summaries/stage8746_contamination_leakage_detector_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CONTAMINATION_LEAKAGE_DETECTOR_GRAPH_ATTACHMENT_STAGE8747.md"

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
    module = "support_module:contamination_leakage_detector"
    added_nodes = int(add_node(nodes, {
        "id": module,
        "kind": "support_module",
        "node_type": "support_module",
        "name": "contamination_leakage_detector",
        "status": "ready_partial_unified_leakage_contract",
        "summary": str(SOURCE.relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    routes = [
        "PASS_NO_CONTAMINATION",
        "BLOCK_TARGET_LEAK",
        "BLOCK_LABEL_CODED_ID",
        "BLOCK_HELDOUT_OVERLAP",
        "BLOCK_BODY_OR_SOURCE_LEAK",
        "REVIEW_SPLIT_OVERLAP",
        "REVIEW_SUSPICIOUS_PROXY",
    ]
    for route in routes:
        node_id = f"contamination_route:{route}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "contamination_route", "node_type": "contamination_route", "status": "row_route", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "may_emit_route", node_id)
    gates = [
        "gate:contamination_detector_blocks_target_leak",
        "gate:contamination_detector_blocks_label_coded_ids",
        "gate:contamination_detector_blocks_heldout_overlap",
        "gate:contamination_detector_blocks_body_or_source_leak",
        "gate:contamination_detector_reviews_split_overlap",
        "gate:contamination_detector_reviews_shortcut_proxies",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for upstream in [
        "control_contract:stage8660_leakage_retrieval_locked_eval",
        "support_module:source_inventory_lineage_tracker",
        "support_module:source_provenance_license_security_filter",
        "support_module:shortcut_baseline_audit",
        "support_module:objective_row_judge",
        "support_module:adversarial_hard_negative_generator",
    ]:
        add_node(nodes, {"id": upstream, "kind": "support_or_contract", "node_type": "support_or_contract", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in [
        "support_module:curriculum_compiler",
        "support_module:dataset_junk_ood_ranker_v1",
        "objective:intent_to_build_strategy",
        "objective:symbol_binding",
        "objective:edit_localization",
        "objective:patch_operator",
        "objective:verifier_repair",
        "objective:bounded_decoder_ce",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "gates", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_contamination_leakage_detector.json"
    nodes_path = OUT_DIR / "central_research_graph_with_contamination_leakage_detector_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_contamination_leakage_detector_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "routes_attached": len(routes), "gates_attached": len(gates), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached contamination_leakage_detector to central graph. Curriculum builders now have a reusable gate for target leaks, label-coded identifiers, heldout overlap, body/source leakage, split overlap, and shortcut proxy review.",
        "next_best_step": "Recover hybrid_retrieval_fusion.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "contamination_leakage_detector_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8747 Contamination Leakage Detector Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached contamination/leakage routes and gates to the central graph.",
        "",
        "The detector gates curriculum compilation and objective builders. It does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness/scoring, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
