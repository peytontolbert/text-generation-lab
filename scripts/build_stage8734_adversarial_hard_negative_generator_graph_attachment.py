#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8734
NAME = "stage8734_adversarial_hard_negative_generator_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8732_denoise_diffusion_repair_contract_graph_attachment/central_research_graph_with_denoise_diffusion_repair_contract.json"
SOURCE = ROOT / "runs/summaries/stage8733_adversarial_hard_negative_generator_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "ADVERSARIAL_HARD_NEGATIVE_GENERATOR_GRAPH_ATTACHMENT_STAGE8734.md"

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
    module = "support_module:adversarial_hard_negative_generator"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "adversarial_hard_negative_generator", "status": "ready_partial_no_authority_generator", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    attacks = ["PROXY_LABEL_SWAP", "EVIDENCE_REMOVED", "LEAK_INJECTION", "DUPLICATE_COLLISION", "MISLEADING_RETRIEVAL"]
    for attack in attacks:
        node_id = f"adversarial_attack:{attack}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "adversarial_attack", "node_type": "adversarial_attack", "status": "ready_negative_generator", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "generates", node_id)
    gates = [
        "gate:adversarial_negatives_never_train_positive",
        "gate:adversarial_negatives_never_enable_losses",
        "gate:adversarial_negatives_never_enable_decode",
        "gate:adversarial_negatives_target_shortcut_audits",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for downstream in [
        "support_module:dataset_junk_ood_ranker_v1",
        "support_module:cluster_slice_near_duplicate_detector",
        "support_module:cross_encoder_reranker_calibration",
        "support_module:curriculum_compiler",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "hardens", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_adversarial_hard_negative_generator.json"
    nodes_path = OUT_DIR / "central_research_graph_with_adversarial_hard_negative_generator_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_adversarial_hard_negative_generator_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": STAGE, "name": NAME, "stage_name": NAME, "passed": bool(source.get("passed")), "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "attacks_attached": len(attacks), "gates_attached": len(gates), "added_nodes": added_nodes}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))}, "decision": "Attached adversarial hard-negative generator to central graph. Generated rows are audit negatives only, not training positives.", "next_best_step": "Recover confidence_ood_head_contract.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "adversarial_hard_negative_generator_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8734 Adversarial Hard-Negative Generator Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached hard-negative attack types and no-authority gates to the central graph.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
