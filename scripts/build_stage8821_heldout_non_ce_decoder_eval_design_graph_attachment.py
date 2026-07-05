#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8821
NAME = "stage8821_heldout_non_ce_decoder_eval_design_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8818_eval_strict_unique_target_gap_graph_attachment/central_research_graph_with_eval_strict_target_gap.json"
SOURCES = [ROOT / "runs/summaries/stage8820_heldout_non_ce_decoder_eval_design_manifest.json"]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "HELDOUT_NON_CE_DECODER_EVAL_DESIGN_GRAPH_ATTACHMENT_STAGE8821.md"
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
    card0 = json.loads(SOURCES[0].read_text(encoding="utf-8"))
    failures = [] if card0.get("passed") is True else [card0.get("stage_name")]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    m = card0.get("metrics", {})
    added_nodes = 0
    design = "objective:heldout_non_ce_decoder_evaluation_design"
    packet = "objective:future_model_output_packet_schema"
    added_nodes += int(add_node(nodes, {"id": design, "kind": "objective", "node_type": "objective", "name": "heldout_non_ce_decoder_evaluation_design", "status": "design_ready_no_execution_not_probe_ready", "summary": str(SOURCES[0].relative_to(ROOT)), "rows": m.get("rows"), "split_counts": m.get("split_counts"), "authority": AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {"id": packet, "kind": "objective", "node_type": "objective", "name": "future_model_output_packet_schema", "status": "missing_next_recovery_target", "purpose": "Define the non-executing packet future probes must emit so heldout non-CE eval can run without CE targets, runtime, Gemma, or scoring authority.", "authority": AUTHORITY_CLOSED}))
    for node_id in ["gap:eval_strict_unique_target_materialization", "objective:bounded_decoder_ce", "study_path:transformer_tiny_model_intelligence", "support_module:traced_eval_observability", "support_module:gradient_activation_interpretability", "support_module:golden_locked_eval_suite"]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "gap:eval_strict_unique_target_materialization", "resolved_by_design_option", design)
    add_edge(edges, design, "requires_before_probe", packet)
    add_edge(edges, packet, "feeds_non_ce_eval_for", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:traced_eval_observability", "must_record", packet)
    add_edge(edges, "support_module:gradient_activation_interpretability", "should_record_shape_loss_telemetry_for", packet)
    add_edge(edges, "study_path:transformer_tiny_model_intelligence", "defines_debug_checklist_for", packet)
    add_edge(edges, "support_module:golden_locked_eval_suite", "guards", design)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_heldout_non_ce_decoder_eval_design.json"
    nodes_path = OUT_DIR / "central_research_graph_with_heldout_non_ce_decoder_eval_design_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_heldout_non_ce_decoder_eval_design_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added_nodes, "heldout_eval_rows": m.get("rows"), "probe_ready_rows": m.get("probe_ready_rows"), "loss_rows": m.get("loss_rows"), "decoder_ce_eligible_now_rows": m.get("decoder_ce_eligible_now_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "design_summary": str(SOURCES[0].relative_to(ROOT))}, "decision": "Attached heldout non-CE decoder eval design to graph; next missing target is future model-output packet schema/telemetry.", "next_best_step": "Build future model-output packet schema/telemetry contract before any tiny probe. Keep execution/training/CE closed.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "heldout_non_ce_decoder_eval_design_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8821 Heldout Non-CE Decoder Eval Design Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Rows: `{metrics['heldout_eval_rows']}`", f"Probe-ready rows: `{metrics['probe_ready_rows']}`", f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`", "", "The graph now records heldout non-CE decoder eval design and the next missing future model-output packet schema.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
