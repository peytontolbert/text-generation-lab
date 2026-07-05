#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8804
NAME = "stage8804_closed_bounded_decoder_ce_gate_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8799_bounded_decoder_argument_controls_graph_attachment/central_research_graph_with_bounded_decoder_argument_controls.json"
SOURCES = [
    ROOT / "runs/summaries/stage8802_closed_bounded_decoder_ce_package_gate.json",
    ROOT / "runs/summaries/stage8803_closed_bounded_decoder_ce_package_gate_audit.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "CLOSED_BOUNDED_DECODER_CE_GATE_GRAPH_ATTACHMENT_STAGE8804.md"
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
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    package, audit = summaries
    failures = [s.get("stage_name") for s in summaries if s.get("passed") is not True]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    objective = "objective:bounded_decoder_ce"
    gate = "gate:closed_bounded_decoder_ce_package"
    audit_node = "audit:closed_bounded_decoder_ce_package_gate"
    materialization = "objective:source_backed_decoder_target_materialization"
    added_nodes += int(add_node(nodes, {
        "id": objective,
        "kind": "objective",
        "node_type": "objective",
        "name": "bounded_decoder_ce",
        "status": "blocked_by_closed_gate_pending_source_backed_target_materialization",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "decoder_ce_eligible_now_rows": audit.get("metrics", {}).get("decoder_ce_eligible_now_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": gate,
        "kind": "gate",
        "node_type": "gate",
        "name": "closed_bounded_decoder_ce_package_gate",
        "status": "passed_no_training_no_ce",
        "summary": str(SOURCES[0].relative_to(ROOT)),
        "rows": package.get("metrics", {}).get("rows"),
        "gate_decision_counts": package.get("metrics", {}).get("gate_decision_counts"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": audit_node,
        "kind": "audit",
        "node_type": "audit",
        "name": "closed_bounded_decoder_ce_package_gate_audit",
        "status": "passed_ce_still_closed",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": materialization,
        "kind": "objective",
        "node_type": "objective",
        "name": "source_backed_decoder_target_materialization",
        "status": "missing_next_recovery_target",
        "purpose": "Materialize decoder target text from source-backed verified structures without exposing target text in encoder input.",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in ["objective:bounded_decoder_arguments", "support_module:curriculum_compiler", "support_module:source_provenance", "support_module:contamination_leakage_detector"]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:bounded_decoder_arguments", "feeds_closed_gate", gate)
    add_edge(edges, gate, "blocks_training_for", objective)
    add_edge(edges, audit_node, "audits", gate)
    add_edge(edges, gate, "requires_before_reopen", materialization)
    add_edge(edges, "support_module:curriculum_compiler", "must_enforce_gate_for", gate)
    add_edge(edges, "support_module:source_provenance", "must_validate_before", materialization)
    add_edge(edges, "support_module:contamination_leakage_detector", "must_validate_before", materialization)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_closed_bounded_decoder_ce_gate.json"
    nodes_path = OUT_DIR / "central_research_graph_with_closed_bounded_decoder_ce_gate_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_closed_bounded_decoder_ce_gate_edges.jsonl"
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
        "closed_ce_gate_rows": package.get("metrics", {}).get("rows"),
        "decoder_ce_eligible_now_rows": audit.get("metrics", {}).get("decoder_ce_eligible_now_rows"),
        "loss_mask_rows": audit.get("metrics", {}).get("loss_mask_rows"),
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
        },
        "decision": "Attached closed bounded decoder CE gate to central graph; bounded decoder CE remains blocked pending target materialization controls." if not failures else "Closed bounded decoder CE gate graph attachment failed.",
        "next_best_step": "Recover source-backed decoder target materialization controls. Do not enable decoder CE or runtime.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "closed_bounded_decoder_ce_gate_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8804 Closed Bounded Decoder CE Gate Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Closed CE gate rows: `{metrics['closed_ce_gate_rows']}`",
        f"Decoder CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        f"Loss-mask rows: `{metrics['loss_mask_rows']}`",
        "",
        "The graph now records that bounded decoder CE is blocked by a passed closed gate until source-backed decoder target materialization controls exist.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
