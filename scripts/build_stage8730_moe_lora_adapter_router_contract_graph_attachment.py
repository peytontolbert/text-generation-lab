#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = 8730
NAME = "stage8730_moe_lora_adapter_router_contract_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8728_fusion_logits_forward_pass_contract_graph_attachment/central_research_graph_with_fusion_logits_forward_pass_contract.json"
SOURCE = ROOT / "runs/summaries/stage8729_moe_lora_adapter_router_contract_readiness.json"
OUT_DIR = ROOT / "runs" / "local" / "artifacts" / NAME
SUMMARY = ROOT / "runs" / "summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MOE_LORA_ADAPTER_ROUTER_CONTRACT_GRAPH_ATTACHMENT_STAGE8730.md"

AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "adapter_training_authorized_next": False,
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
    module = "support_module:moe_lora_adapter_router_contract"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "moe_lora_adapter_router_contract", "status": "ready_partial_no_execution_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    signals = [
        "adapter_router_signal:language_family",
        "adapter_router_signal:task_family",
        "adapter_router_signal:repo_family",
        "adapter_router_signal:slice_readiness",
        "adapter_router_signal:slice_confidence",
        "adapter_router_signal:ood_leak_authority",
    ]
    for signal in signals:
        added_nodes += int(add_node(nodes, {"id": signal, "kind": "adapter_router_signal", "node_type": "adapter_router_signal", "status": "required_input", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, signal, "feeds", module)
    routes = [
        "adapter_route:USE_BASE_SHARED",
        "adapter_route:ROUTE_LANGUAGE_ADAPTER_SHADOW",
        "adapter_route:ROUTE_TASK_ADAPTER_SHADOW",
        "adapter_route:ROUTE_REPO_ADAPTER_SHADOW",
        "adapter_route:ROUTE_COMPOSED_ADAPTER_SHADOW",
        "adapter_route:REQUEST_SLICE_EVIDENCE",
        "adapter_route:ABSTAIN_ADAPTER_ROUTE",
    ]
    for route in routes:
        added_nodes += int(add_node(nodes, {"id": route, "kind": "adapter_route", "node_type": "adapter_route", "status": "safe_shadow_route", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "may_emit_route", route)
    gates = [
        "gate:adapter_router_never_authorizes_training",
        "gate:adapter_router_never_authorizes_model_execution",
        "gate:adapter_router_never_authorizes_decoder_ce",
        "gate:adapter_shadow_requires_slice_readiness",
        "gate:adapter_authority_or_ood_forces_abstain",
    ]
    for gate in gates:
        added_nodes += int(add_node(nodes, {"id": gate, "kind": "gate", "node_type": "gate", "status": "active_contract", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, gate, "guards", module)
    for upstream in [
        "model_family:moe_lora_adapters",
        "support_module:fusion_logits_forward_pass_contract",
        "support_module:dataset_cartography_active_learning",
        "support_module:confidence_ood_head_contract",
    ]:
        add_node(nodes, {"id": upstream, "kind": "support_or_model_family", "node_type": "support_or_model_family", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["objective:bounded_decoder_ce", "objective:output_repair_denoise", "support_module:curriculum_compiler"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "gates", downstream)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_moe_lora_adapter_router_contract.json"
    nodes_path = OUT_DIR / "central_research_graph_with_moe_lora_adapter_router_contract_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_moe_lora_adapter_router_contract_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "name": NAME,
        "stage_name": NAME,
        "passed": bool(source.get("passed")),
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "signals_attached": len(signals), "routes_attached": len(routes), "gates_attached": len(gates), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached no-execution MoE/LoRA adapter router contract to central graph. Adapter routes are shadow hints only and cannot authorize adapter training, model execution, or decoder CE.",
        "next_best_step": "Recover denoise_diffusion_repair_contract.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "moe_lora_adapter_router_contract_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8730 MoE/LoRA Adapter Router Contract Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached no-execution adapter-router signals, routes, and hard authority gates to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
