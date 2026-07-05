#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8744
NAME = "stage8744_source_provenance_license_security_filter_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8742_source_inventory_lineage_tracker_graph_attachment/central_research_graph_with_source_inventory_lineage_tracker.json"
SOURCE = ROOT / "runs/summaries/stage8743_source_provenance_license_security_filter_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_PROVENANCE_LICENSE_SECURITY_FILTER_GRAPH_ATTACHMENT_STAGE8744.md"

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
    module = "support_module:source_provenance_license_security_filter"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "source_provenance_license_security_filter", "status": "ready_partial_source_admission_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    routes = ["ALLOW_SOURCE_FOR_STRUCTURED", "ALLOW_SOURCE_FOR_HOLDOUT_ONLY", "HOLD_LICENSE_REVIEW", "HOLD_SECURITY_REVIEW", "BLOCK_SECRET_OR_PII", "BLOCK_LOCKED_EVAL_TRAIN", "BLOCK_DISALLOWED_IMPORT_SOURCE", "BLOCK_MISSING_LINEAGE"]
    for route in routes:
        node_id = f"source_filter_route:{route}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "source_filter_route", "node_type": "source_filter_route", "status": "source_admission_route", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "may_emit_route", node_id)
    gates = [
        "gate:source_filter_requires_lineage",
        "gate:source_filter_blocks_secret_or_pii",
        "gate:source_filter_blocks_locked_eval_train",
        "gate:source_filter_reviews_unknown_license",
        "gate:source_filter_reviews_missing_security_policy",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for upstream in ["support_module:source_inventory_lineage_tracker", "support_module:secret_pii_leak_detector", "support_module:static_analysis_security_scanner"]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["support_module:curriculum_compiler", "support_module:dataset_junk_ood_ranker_v1", "objective:symbol_binding", "objective:bounded_decoder_ce"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "gates", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_source_provenance_license_security_filter.json"
    nodes_path = OUT_DIR / "central_research_graph_with_source_provenance_license_security_filter_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_source_provenance_license_security_filter_edges.jsonl"
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
        "decision": "Attached source provenance/license/security filter to central graph. Source admission now depends on lineage, license, security policy, import-source status, and secret/PII screening.",
        "next_best_step": "Recover contamination_leakage_detector.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "source_provenance_license_security_filter_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8744 Source Provenance License Security Filter Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached source provenance/license/security routes and gates to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
