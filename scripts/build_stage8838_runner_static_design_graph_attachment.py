#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8838
NAME = "stage8838_runner_static_design_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8835_model_output_capture_preflight_audit_graph_attachment/central_research_graph_with_model_output_capture_preflight_audit.json"
SOURCE = ROOT / "runs/summaries/stage8837_model_output_capture_runner_static_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RUNNER_STATIC_DESIGN_GRAPH_ATTACHMENT_STAGE8838.md"
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
    design = "design:future_model_output_capture_runner_static_v1"
    ticket = "objective:future_model_output_capture_authority_ticket_schema"
    added += int(add_node(nodes, {
        "id": design,
        "kind": "design",
        "node_type": "design",
        "name": "future_model_output_capture_runner_static_v1",
        "status": "static_design_ready_no_execution",
        "rows": m.get("rows"),
        "runner_static_design_ready_rows": m.get("runner_static_design_ready_rows"),
        "execution_open_rows": m.get("execution_open_rows"),
        "model_output_rows": m.get("model_output_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": ticket,
        "kind": "objective",
        "node_type": "objective",
        "name": "future_model_output_capture_authority_ticket_schema",
        "status": "missing_next_recovery_target",
        "purpose": "Define explicit authority fields required before any future checkpoint load, forward pass, decode, or output artifact write can be considered.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        "objective:future_model_output_capture_runner_static_design",
        "objective:authority_closed_model_output_capture_preflight",
        "contract:model_output_packet_telemetry_v1",
        "support_module:traced_eval_observability",
        "support_module:golden_locked_eval_suite",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:future_model_output_capture_runner_static_design", "materialized_by_design", design)
    add_edge(edges, "objective:authority_closed_model_output_capture_preflight", "precedes", design)
    add_edge(edges, design, "requires_before_any_execution", ticket)
    add_edge(edges, ticket, "required_before", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:traced_eval_observability", "must_record_authority_ticket_for", ticket)
    add_edge(edges, "support_module:golden_locked_eval_suite", "guards", ticket)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_runner_static_design.json"
    nodes_path = OUT_DIR / "central_research_graph_with_runner_static_design_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_runner_static_design_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "runner_static_rows": m.get("rows"), "runner_static_design_ready_rows": m.get("runner_static_design_ready_rows"), "execution_open_rows": m.get("execution_open_rows"), "model_output_rows": m.get("model_output_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "runner_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached future runner static design to graph; next missing target is authority-ticket schema.", "next_best_step": "Recover authority-ticket schema for future model-output capture. Do not run a model yet.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "runner_static_design_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8838 Runner Static Design Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Runner static rows: `{metrics['runner_static_rows']}`", f"Execution-open rows: `{metrics['execution_open_rows']}`", f"Model output rows: `{metrics['model_output_rows']}`", "", "The graph now records the future runner static design and authority-ticket schema target.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
