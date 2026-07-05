#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8848
NAME = "stage8848_learning_signal_implementation_plan_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8845_learning_signal_contract_graph_attachment/central_research_graph_with_learning_signal_contract.json"
SOURCE = ROOT / "runs/summaries/stage8847_learning_signal_implementation_plan.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "LEARNING_SIGNAL_IMPLEMENTATION_PLAN_GRAPH_ATTACHMENT_STAGE8848.md"
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
    plan = "plan:learning_signal_dataset_trainer_implementation_v1"
    audit = "objective:learning_signal_implementation_plan_gate_audit"
    added += int(add_node(nodes, {
        "id": plan,
        "kind": "plan",
        "node_type": "plan",
        "name": "learning_signal_dataset_trainer_implementation_v1",
        "status": "plan_ready_no_code_patch_no_training",
        "rows": m.get("rows"),
        "ready_rows": m.get("implementation_plan_ready_rows"),
        "file_counts": m.get("file_counts"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": audit,
        "kind": "objective",
        "node_type": "objective",
        "name": "learning_signal_implementation_plan_gate_audit",
        "status": "missing_next_recovery_target",
        "purpose": "Audit that the implementation plan has complete file touchpoints, acceptance checks, and no training/decoder authority.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        "contract:learning_signal_improvement_v1",
        "objective:learning_signal_dataset_trainer_implementation_plan",
        "file:legacy_src/agentkernel_lite/training_data.py",
        "file:legacy_src/agentkernel_lite/training_loop.py",
        "file:scripts/training_telemetry_metrics.py",
        "file:legacy_src/agentkernel_lite/modeling_transformer.py",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_file", "node_type": "support_or_file", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:learning_signal_dataset_trainer_implementation_plan", "materialized_by_plan", plan)
    add_edge(edges, "contract:learning_signal_improvement_v1", "implemented_by_future_plan", plan)
    add_edge(edges, plan, "required_before", audit)
    for file_node in [
        "file:legacy_src/agentkernel_lite/training_data.py",
        "file:legacy_src/agentkernel_lite/training_loop.py",
        "file:scripts/training_telemetry_metrics.py",
        "file:legacy_src/agentkernel_lite/modeling_transformer.py",
    ]:
        add_edge(edges, plan, "touches_file", file_node)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_learning_signal_implementation_plan.json"
    nodes_path = OUT_DIR / "central_research_graph_with_learning_signal_implementation_plan_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_learning_signal_implementation_plan_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "plan_rows": m.get("rows"), "plan_ready_rows": m.get("implementation_plan_ready_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "plan_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached learning-signal implementation plan to graph; next missing target is plan gate audit.", "next_best_step": "Recover implementation-plan gate audit. Keep training and decoder CE closed.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "learning_signal_implementation_plan_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8848 Learning Signal Implementation Plan Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Plan rows: `{metrics['plan_rows']}`", f"Ready rows: `{metrics['plan_ready_rows']}`", "", "The graph now records the implementation-plan artifact and gate-audit target.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
