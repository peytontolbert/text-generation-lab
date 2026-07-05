#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8841
NAME = "stage8841_authority_ticket_schema_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8838_runner_static_design_graph_attachment/central_research_graph_with_runner_static_design.json"
SOURCE = ROOT / "runs/summaries/stage8840_authority_ticket_schema.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "AUTHORITY_TICKET_SCHEMA_GRAPH_ATTACHMENT_STAGE8841.md"
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
    schema = "schema:model_output_capture_authority_ticket_v1"
    audit = "objective:authority_ticket_schema_gate_audit"
    added += int(add_node(nodes, {
        "id": schema,
        "kind": "schema",
        "node_type": "schema",
        "name": "model_output_capture_authority_ticket_v1",
        "status": "schema_ready_closed_by_default",
        "rows": m.get("rows"),
        "ready_rows": m.get("authority_ticket_schema_ready_rows"),
        "allowed_operation_rows": m.get("allowed_operation_rows"),
        "opening_rows": m.get("opening_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": audit,
        "kind": "objective",
        "node_type": "objective",
        "name": "authority_ticket_schema_gate_audit",
        "status": "missing_next_recovery_target",
        "purpose": "Audit authority-ticket schema invariants before any future runner or ticket instance can be considered.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        "objective:future_model_output_capture_authority_ticket_schema",
        "design:future_model_output_capture_runner_static_v1",
        "objective:bounded_decoder_ce",
        "support_module:traced_eval_observability",
        "support_module:golden_locked_eval_suite",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:future_model_output_capture_authority_ticket_schema", "materialized_by_schema", schema)
    add_edge(edges, "design:future_model_output_capture_runner_static_v1", "requires_ticket_schema", schema)
    add_edge(edges, schema, "required_before", audit)
    add_edge(edges, audit, "required_before_any_execution_for", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:traced_eval_observability", "must_record_ticket_for", schema)
    add_edge(edges, "support_module:golden_locked_eval_suite", "guards", audit)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_authority_ticket_schema.json"
    nodes_path = OUT_DIR / "central_research_graph_with_authority_ticket_schema_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_authority_ticket_schema_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "ticket_schema_rows": m.get("rows"), "ticket_ready_rows": m.get("authority_ticket_schema_ready_rows"), "allowed_operation_rows": m.get("allowed_operation_rows"), "opening_rows": m.get("opening_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "ticket_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached authority-ticket schema to graph; next missing target is ticket schema gate audit.", "next_best_step": "Audit authority-ticket schema gates. Do not run a model yet.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "authority_ticket_schema_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8841 Authority Ticket Schema Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Ticket schema rows: `{metrics['ticket_schema_rows']}`", f"Ticket ready rows: `{metrics['ticket_ready_rows']}`", f"Allowed-operation rows: `{metrics['allowed_operation_rows']}`", "", "The graph now records the closed-by-default authority-ticket schema and its gate audit target.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
