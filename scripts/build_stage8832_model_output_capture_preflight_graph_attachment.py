#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8832
NAME = "stage8832_model_output_capture_preflight_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8829_synthetic_packet_validator_graph_attachment/central_research_graph_with_synthetic_packet_validator.json"
SOURCE = ROOT / "runs/summaries/stage8831_model_output_capture_preflight_design.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_CAPTURE_PREFLIGHT_GRAPH_ATTACHMENT_STAGE8832.md"
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
    design = "design:authority_closed_model_output_capture_preflight_v1"
    gate = "objective:static_capture_preflight_gate_audit"
    added += int(add_node(nodes, {
        "id": design,
        "kind": "design",
        "node_type": "design",
        "name": "authority_closed_model_output_capture_preflight_v1",
        "status": "design_ready_no_execution",
        "rows": m.get("rows"),
        "ready_for_model_execution_rows": m.get("ready_for_model_execution_rows"),
        "model_output_rows": m.get("model_output_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": gate,
        "kind": "objective",
        "node_type": "objective",
        "name": "static_capture_preflight_gate_audit",
        "status": "missing_next_recovery_target",
        "purpose": "Static gate over the capture preflight design before any model-output capture path can be considered.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        "objective:authority_closed_model_output_capture_preflight",
        "validator:synthetic_packet_validator_dry_run_v1",
        "contract:model_output_packet_telemetry_v1",
        "support_module:traced_eval_observability",
        "support_module:golden_locked_eval_suite",
        "objective:bounded_decoder_ce",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:authority_closed_model_output_capture_preflight", "materialized_by_design", design)
    add_edge(edges, "validator:synthetic_packet_validator_dry_run_v1", "precedes", design)
    add_edge(edges, design, "required_before", gate)
    add_edge(edges, gate, "required_before_any_model_output_for", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:traced_eval_observability", "must_capture_audit_for", gate)
    add_edge(edges, "support_module:golden_locked_eval_suite", "guards", gate)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_model_output_capture_preflight.json"
    nodes_path = OUT_DIR / "central_research_graph_with_model_output_capture_preflight_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_model_output_capture_preflight_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "preflight_rows": m.get("rows"), "model_output_rows": m.get("model_output_rows"), "ready_for_model_execution_rows": m.get("ready_for_model_execution_rows"), "ready_for_decoder_ce_rows": m.get("ready_for_decoder_ce_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "preflight_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached authority-closed model-output capture preflight design to graph; next missing target is static preflight gate audit.", "next_best_step": "Build static capture preflight gate audit. Keep model execution/training/CE closed.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "model_output_capture_preflight_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8832 Model Output Capture Preflight Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Preflight rows: `{metrics['preflight_rows']}`", f"Model output rows: `{metrics['model_output_rows']}`", f"Ready for model execution rows: `{metrics['ready_for_model_execution_rows']}`", "", "The graph now records the authority-closed capture preflight design and static gate audit target.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
