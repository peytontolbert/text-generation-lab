#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8738
NAME = "stage8738_structured_data_operation_curriculum_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8736_confidence_ood_head_contract_graph_attachment/central_research_graph_with_confidence_ood_head_contract.json"
SOURCE = ROOT / "runs/summaries/stage8737_structured_data_operation_curriculum_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STRUCTURED_DATA_OPERATION_CURRICULUM_GRAPH_ATTACHMENT_STAGE8738.md"

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
    module = "support_module:structured_data_operation_curriculum"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "structured_data_operation_curriculum", "status": "ready_partial_structured_only_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    structures = ["table", "json", "graph", "ast", "log_trace", "workflow", "memory"]
    for structure in structures:
        node_id = f"structured_modality:{structure}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "structured_modality", "node_type": "structured_modality", "status": "seed_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, node_id, "covered_by", module)
    gates = [
        "gate:structured_operations_require_schema",
        "gate:structured_operations_require_addressing",
        "gate:structured_operations_require_validator",
        "gate:structured_operations_never_enable_decoder_ce",
        "gate:structured_operations_never_enable_runtime_reward",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for downstream in [
        "support_module:curriculum_compiler",
        "objective:state_field_denoise",
        "objective:patch_operator",
        "objective:verifier_repair",
        "objective:bounded_decoder_ce",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "feeds", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_structured_data_operation_curriculum.json"
    nodes_path = OUT_DIR / "central_research_graph_with_structured_data_operation_curriculum_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_structured_data_operation_curriculum_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "structures_attached": len(structures), "gates_attached": len(gates), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached structured data operation curriculum to central graph. Structured operations are schema/address/validator bound and cannot enable decoder CE or runtime reward.",
        "next_best_step": "Recover semantic_equivalence_metamorphic_verifier.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "structured_data_operation_curriculum_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8738 Structured Data Operation Curriculum Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached structured modalities and schema/address/validator gates to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
