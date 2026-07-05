#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8742
NAME = "stage8742_source_inventory_lineage_tracker_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8738_structured_data_operation_curriculum_graph_attachment/central_research_graph_with_structured_data_operation_curriculum.json"
SOURCE = ROOT / "runs/summaries/stage8741_source_inventory_lineage_tracker_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_INVENTORY_LINEAGE_TRACKER_GRAPH_ATTACHMENT_STAGE8742.md"

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
    module = "support_module:source_inventory_lineage_tracker"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "source_inventory_lineage_tracker", "status": "ready_partial_reusable_lineage_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    fields = ["source_id", "content_hash", "transform_chain", "split_eligibility", "lineage_hash", "license_status", "security_policy_present"]
    for field in fields:
        node_id = f"lineage_field:{field}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "lineage_field", "node_type": "lineage_field", "status": "required_field", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, node_id, "required_by", module)
    gates = [
        "gate:lineage_required_before_mining",
        "gate:locked_eval_never_train_eligible",
        "gate:unknown_license_blocks_train_without_review",
        "gate:missing_security_policy_blocks_external_train_source",
        "gate:lineage_hash_required_for_split_admission",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for downstream in ["support_module:curriculum_compiler", "support_module:dataset_junk_ood_ranker_v1", "objective:symbol_binding", "objective:patch_operator", "objective:bounded_decoder_ce"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "gates", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_source_inventory_lineage_tracker.json"
    nodes_path = OUT_DIR / "central_research_graph_with_source_inventory_lineage_tracker_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_source_inventory_lineage_tracker_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "fields_attached": len(fields), "gates_attached": len(gates), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached source inventory lineage tracker to central graph. All future mined rows must carry lineage fields and split eligibility before curriculum admission.",
        "next_best_step": "Recover source_provenance_license_security_filter.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "source_inventory_lineage_tracker_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8742 Source Inventory Lineage Tracker Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached source lineage fields and split/admission gates to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
