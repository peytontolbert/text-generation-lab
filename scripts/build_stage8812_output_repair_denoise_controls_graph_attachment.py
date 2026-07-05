#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8812
NAME = "stage8812_output_repair_denoise_controls_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8804_closed_bounded_decoder_ce_gate_graph_attachment/central_research_graph_with_closed_bounded_decoder_ce_gate.json"
SOURCES = [
    ROOT / "runs/summaries/stage8810_output_repair_denoise_controls_manifest.json",
    ROOT / "runs/summaries/stage8811_output_repair_denoise_controls_shortcut_gate.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "OUTPUT_REPAIR_DENOISE_CONTROLS_GRAPH_ATTACHMENT_STAGE8812.md"
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
    manifest, audit = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    failures = [s.get("stage_name") for s in [manifest, audit] if s.get("passed") is not True]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    objective = "objective:output_repair_denoise_controls"
    denoise = "objective:denoise_repair"
    gate = "gate:output_repair_denoise_shortcut_gate"
    materialization = "objective:verifier_guided_repair_target_materialization"
    added_nodes += int(add_node(nodes, {
        "id": objective,
        "kind": "objective",
        "node_type": "objective",
        "name": "output_repair_denoise_controls",
        "status": "candidate_controls_audit_passed_no_training",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "rows": audit.get("metrics", {}).get("rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": denoise,
        "kind": "objective",
        "node_type": "objective",
        "name": "denoise_repair",
        "status": "blocked_by_closed_controls_pending_verifier_guided_materialization",
        "denoise_ce_eligible_now_rows": audit.get("metrics", {}).get("denoise_ce_eligible_now_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": gate,
        "kind": "gate",
        "node_type": "gate",
        "name": "output_repair_denoise_shortcut_gate",
        "status": "passed_no_denoise_ce",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "max_proxy_single": audit.get("metrics", {}).get("max_proxy_single"),
        "max_proxy_combo": audit.get("metrics", {}).get("max_proxy_combo"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": materialization,
        "kind": "objective",
        "node_type": "objective",
        "name": "verifier_guided_repair_target_materialization",
        "status": "missing_next_recovery_target_after_target_text_controls",
        "purpose": "Materialize masked repair targets from verifier feedback and source-backed structured state without exposing target text in encoder input.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in ["objective:bounded_decoder_ce", "objective:source_backed_decoder_target_materialization", "support_module:traced_eval_observability", "support_module:curriculum_compiler", "support_module:semantic_equivalence_metamorphic_verifier"]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:bounded_decoder_ce", "feeds_failures_to", objective)
    add_edge(edges, objective, "passes_closed_gate", gate)
    add_edge(edges, gate, "blocks_denoise_ce_for", denoise)
    add_edge(edges, denoise, "requires_before_reopen", materialization)
    add_edge(edges, "objective:source_backed_decoder_target_materialization", "precedes", materialization)
    add_edge(edges, "support_module:traced_eval_observability", "provides_failure_packets_for", objective)
    add_edge(edges, "support_module:curriculum_compiler", "must_enforce_gate_for", objective)
    add_edge(edges, "support_module:semantic_equivalence_metamorphic_verifier", "must_verify_repair_targets_for", materialization)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_output_repair_denoise_controls.json"
    nodes_path = OUT_DIR / "central_research_graph_with_output_repair_denoise_controls_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_output_repair_denoise_controls_edges.jsonl"
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
        "output_repair_denoise_rows": audit.get("metrics", {}).get("rows"),
        "denoise_ce_eligible_now_rows": audit.get("metrics", {}).get("denoise_ce_eligible_now_rows"),
        "loss_rows": audit.get("metrics", {}).get("loss_rows"),
        "max_proxy_single": audit.get("metrics", {}).get("max_proxy_single"),
        "max_proxy_combo": audit.get("metrics", {}).get("max_proxy_combo"),
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached output repair/denoise controls to central graph; denoise CE remains blocked pending verifier-guided repair target materialization." if not failures else "Output repair/denoise graph attachment failed.",
        "next_best_step": "After source-backed decoder target materialization, recover verifier-guided repair target materialization controls. Do not enable denoise CE.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "output_repair_denoise_controls_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8812 Output Repair Denoise Controls Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Rows: `{metrics['output_repair_denoise_rows']}`",
        f"Denoise CE eligible now rows: `{metrics['denoise_ce_eligible_now_rows']}`",
        f"Loss rows: `{metrics['loss_rows']}`",
        f"Max proxy single: `{metrics['max_proxy_single']}`",
        f"Max proxy combo: `{metrics['max_proxy_combo']}`",
        "",
        "Denoise repair is now represented as a closed controls objective. Denoise CE remains blocked.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
