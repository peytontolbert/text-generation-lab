#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8835
NAME = "stage8835_model_output_capture_preflight_audit_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8832_model_output_capture_preflight_graph_attachment/central_research_graph_with_model_output_capture_preflight.json"
SOURCE = ROOT / "runs/summaries/stage8834_model_output_capture_preflight_design_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "MODEL_OUTPUT_CAPTURE_PREFLIGHT_AUDIT_GRAPH_ATTACHMENT_STAGE8835.md"
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
    card_src = json.loads(SOURCE.read_text(encoding="utf-8"))
    failures = [] if card_src.get("passed") is True else [card_src.get("stage_name")]
    m = card_src.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added = 0
    audit_node = "audit:model_output_capture_preflight_design_audit"
    runner_design = "objective:future_model_output_capture_runner_static_design"
    added += int(add_node(nodes, {"id": audit_node, "kind": "audit", "node_type": "audit", "name": "model_output_capture_preflight_design_audit", "status": "passed_closed_authority", "rows": m.get("rows"), "audit_ready_rows": m.get("audit_ready_rows"), "execution_allowed_rows": m.get("execution_allowed_rows"), "model_output_rows": m.get("model_output_rows"), "artifact_write_rows": m.get("artifact_write_rows"), "authority": AUTHORITY_CLOSED}))
    added += int(add_node(nodes, {"id": runner_design, "kind": "objective", "node_type": "objective", "name": "future_model_output_capture_runner_static_design", "status": "missing_next_recovery_target", "purpose": "Define static CLI/interface checks for a future no-training output-capture runner without authorizing execution.", "authority": AUTHORITY_CLOSED}))
    for node_id in ["objective:authority_closed_model_output_capture_preflight", "objective:bounded_decoder_ce", "support_module:traced_eval_observability", "support_module:golden_locked_eval_suite"]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:authority_closed_model_output_capture_preflight", "audited_by", audit_node)
    add_edge(edges, audit_node, "unblocks_static_design_of", runner_design)
    add_edge(edges, runner_design, "required_before_any_model_output_for", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:traced_eval_observability", "must_define_artifacts_for", runner_design)
    add_edge(edges, "support_module:golden_locked_eval_suite", "guards", runner_design)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_model_output_capture_preflight_audit.json"
    nodes_path = OUT_DIR / "central_research_graph_with_model_output_capture_preflight_audit_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_model_output_capture_preflight_audit_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "audit_ready_rows": m.get("audit_ready_rows"), "execution_allowed_rows": m.get("execution_allowed_rows"), "model_output_rows": m.get("model_output_rows"), "artifact_write_rows": m.get("artifact_write_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "audit_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached closed-authority preflight audit to graph; next missing target is static runner interface design.", "next_best_step": "Build future model-output capture runner static design. Do not run a model yet.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "model_output_capture_preflight_audit_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8835 Model Output Capture Preflight Audit Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Audit-ready rows: `{metrics['audit_ready_rows']}`", f"Execution-allowed rows: `{metrics['execution_allowed_rows']}`", f"Model output rows: `{metrics['model_output_rows']}`", "", "The graph now records the passed preflight audit and the next static runner-interface design target.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
