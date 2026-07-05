#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8845
NAME = "stage8845_learning_signal_contract_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8841_authority_ticket_schema_graph_attachment/central_research_graph_with_authority_ticket_schema.json"
SOURCE = ROOT / "runs/summaries/stage8844_learning_signal_contract.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_CONTRACT_GRAPH_ATTACHMENT_STAGE8845.md"
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
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    src = json.loads(SOURCE.read_text(encoding="utf-8"))
    failures = [] if src.get("passed") is True else [src.get("stage_name")]
    m = src.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added = 0
    contract = "contract:learning_signal_improvement_v1"
    plan = "objective:learning_signal_dataset_trainer_implementation_plan"
    added += int(add_node(nodes, {
        "id": contract,
        "kind": "contract",
        "node_type": "contract",
        "name": "learning_signal_improvement_v1",
        "status": "contract_ready_no_training",
        "rows": m.get("rows"),
        "ready_rows": m.get("learning_signal_contract_ready_rows"),
        "target_field_counts": m.get("target_field_counts"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": plan,
        "kind": "objective",
        "node_type": "objective",
        "name": "learning_signal_dataset_trainer_implementation_plan",
        "status": "missing_next_recovery_target",
        "purpose": "Define exact file-level changes for typed serialization, counterfactual sibling rows, telemetry, and loss weighting before training resumes.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        "file:legacy_src/agentkernel_lite/training_data.py",
        "file:legacy_src/agentkernel_lite/training_loop.py",
        "file:scripts/training_telemetry_metrics.py",
        "file:legacy_src/agentkernel_lite/modeling_transformer.py",
        "contract:training_tiny_details",
        "study_path:transformer_tiny_model_intelligence",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_file", "node_type": "support_or_file", "authority": AUTHORITY_CLOSED})
    add_edge(edges, contract, "requires_implementation_plan", plan)
    add_edge(edges, contract, "extends", "contract:training_tiny_details")
    add_edge(edges, "file:legacy_src/agentkernel_lite/training_data.py", "must_implement_serialization_for", contract)
    add_edge(edges, "file:legacy_src/agentkernel_lite/training_loop.py", "must_emit_telemetry_for", contract)
    add_edge(edges, "file:scripts/training_telemetry_metrics.py", "supports", contract)
    add_edge(edges, "file:legacy_src/agentkernel_lite/modeling_transformer.py", "provides_heads_for", contract)
    add_edge(edges, "study_path:transformer_tiny_model_intelligence", "grounds", contract)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_learning_signal_contract.json"
    nodes_path = OUT_DIR / "central_research_graph_with_learning_signal_contract_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_learning_signal_contract_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "learning_signal_rows": m.get("rows"), "learning_signal_ready_rows": m.get("learning_signal_contract_ready_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "learning_signal_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached learning-signal contract to graph; next missing target is dataset/trainer implementation plan.", "next_best_step": "Recover dataset/trainer implementation plan for learning-signal improvements. Keep training and decoder CE closed.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "learning_signal_contract_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8845 Learning Signal Contract Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Learning-signal rows: `{metrics['learning_signal_rows']}`", f"Ready rows: `{metrics['learning_signal_ready_rows']}`", "", "The graph now records the typed learning-signal contract and implementation-plan target.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
