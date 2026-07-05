#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8799
NAME = "stage8799_bounded_decoder_argument_controls_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8793_query_recovery_graph_attachment/central_research_graph_with_query_recovery.json"
SOURCES = [
    ROOT / "runs/summaries/stage8797_bounded_decoder_argument_controls_manifest.json",
    ROOT / "runs/summaries/stage8798_bounded_decoder_argument_controls_shortcut_gate.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "BOUNDED_DECODER_ARGUMENT_CONTROLS_GRAPH_ATTACHMENT_STAGE8799.md"
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
    edge = {
        "src": src,
        "edge_type": relation,
        "dst": dst,
        "source": src,
        "relation": relation,
        "target": dst,
        "evidence_source": NAME,
    }
    if edge not in edges:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    manifest, audit = summaries
    failures = [summary.get("stage_name", str(i)) for i, summary in enumerate(summaries) if summary.get("passed") is not True]

    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0

    objective = "objective:bounded_decoder_arguments"
    builder = "builder:bounded_decoder_argument_controls"
    audit_node = "audit:bounded_decoder_argument_controls"

    added_nodes += int(add_node(nodes, {
        "id": objective,
        "kind": "objective",
        "node_type": "objective",
        "name": "bounded_decoder_arguments",
        "status": "candidate_controls_audit_passed_no_training",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "rows": audit.get("metrics", {}).get("rows"),
        "labels": sorted((audit.get("metrics", {}).get("label_counts") or {}).keys()),
        "purpose": "Classify bounded decoder argument intent before any decoder CE or body generation is reopened.",
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": builder,
        "kind": "builder",
        "node_type": "builder",
        "name": "bounded_decoder_argument_controls_builder",
        "status": "ready_no_authority_control_manifest",
        "summary": str(SOURCES[0].relative_to(ROOT)),
        "script": manifest.get("artifacts", {}).get("builder"),
        "manifest": manifest.get("artifacts", {}).get("manifest"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": audit_node,
        "kind": "audit",
        "node_type": "audit",
        "name": "bounded_decoder_argument_controls_audit",
        "status": "passed_shortcut_and_gate_audit",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "max_proxy_single": audit.get("metrics", {}).get("max_proxy_single"),
        "max_proxy_combo": audit.get("metrics", {}).get("max_proxy_combo"),
        "proxy_baseline_ceiling": audit.get("metrics", {}).get("proxy_baseline_ceiling"),
        "authority": AUTHORITY_CLOSED,
    }))

    for node_id in [
        "support_module:curriculum_compiler",
        "support_module:dataset_junk_ood_ranker_v1",
        "support_module:schema_drift_detector",
        "support_module:query_expansion_rewriter",
        "support_module:traced_eval_observability",
        "objective:source_backed_verifier_repair",
        "objective:bounded_decoder_ce",
        "objective:denoise_repair",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})

    add_edge(edges, builder, "builds_no_authority_manifest_for", objective)
    add_edge(edges, audit_node, "audits_shortcut_and_gate_status_for", objective)
    add_edge(edges, "support_module:curriculum_compiler", "requires_gate_status_for", objective)
    add_edge(edges, "support_module:dataset_junk_ood_ranker_v1", "filters_before_training_for", objective)
    add_edge(edges, "support_module:schema_drift_detector", "guards_schema_for", objective)
    add_edge(edges, "support_module:query_expansion_rewriter", "supports_evidence_retrieval_for", objective)
    add_edge(edges, "support_module:traced_eval_observability", "records_eval_trace_for", objective)
    add_edge(edges, "objective:source_backed_verifier_repair", "precedes_and_supports", objective)
    add_edge(edges, objective, "precedes_closed_decoder_ce_package", "objective:bounded_decoder_ce")
    add_edge(edges, objective, "can_feed_future_closed_denoise_repair_controls", "objective:denoise_repair")

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_bounded_decoder_argument_controls.json"
    nodes_path = OUT_DIR / "central_research_graph_with_bounded_decoder_argument_controls_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_bounded_decoder_argument_controls_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")

    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "source_failures": failures,
        "graph_nodes": len(out["nodes"]),
        "graph_edges": len(out["edges"]),
        "added_nodes": added_nodes,
        "bounded_decoder_argument_rows": audit.get("metrics", {}).get("rows"),
        "majority_baseline": audit.get("metrics", {}).get("majority_baseline"),
        "max_proxy_single": audit.get("metrics", {}).get("max_proxy_single"),
        "max_proxy_combo": audit.get("metrics", {}).get("max_proxy_combo"),
        "training_loss_row_count": audit.get("metrics", {}).get("training_loss_rows"),
        "gate_incomplete_row_count": (audit.get("metrics", {}).get("rows", 0) - audit.get("metrics", {}).get("complete_gate_status_rows", 0)),
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
            "manifest_summary": str(SOURCES[0].relative_to(ROOT)),
            "audit_summary": str(SOURCES[1].relative_to(ROOT)),
        },
        "decision": (
            "Attached bounded decoder argument controls to the central graph as a closed no-training objective."
            if not failures else "Bounded decoder argument graph attachment failed."
        ),
        "next_best_step": "Reconcile registry/spine, then build a closed bounded decoder CE package gate without enabling decoder CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "bounded_decoder_argument_controls_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8799 Bounded Decoder Argument Controls Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows attached: `{metrics['bounded_decoder_argument_rows']}`",
        f"Max proxy single: `{metrics['max_proxy_single']}`",
        f"Max proxy combo: `{metrics['max_proxy_combo']}`",
        f"Training loss rows: `{metrics['training_loss_row_count']}`",
        f"Gate incomplete rows: `{metrics['gate_incomplete_row_count']}`",
        "",
        "This attaches bounded decoder argument controls as a closed, no-training objective. It does not authorize decoder CE, denoise CE, model execution, runtime, source/body emission, Gemma, scoring, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
