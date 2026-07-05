#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8808
NAME = "stage8808_source_backed_decoder_target_materialization_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8804_closed_bounded_decoder_ce_gate_graph_attachment/central_research_graph_with_closed_bounded_decoder_ce_gate.json"
SOURCES = [
    ROOT / "runs/summaries/stage8806_source_backed_decoder_target_materialization_controls.json",
    ROOT / "runs/summaries/stage8807_source_backed_decoder_target_materialization_audit.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_DECODER_TARGET_MATERIALIZATION_GRAPH_ATTACHMENT_STAGE8808.md"
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
    cards = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    failures = [card.get("stage_name", str(i)) for i, card in enumerate(cards) if card.get("passed") is not True]
    controls, audit = cards
    cm = controls.get("metrics", {})
    am = audit.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    materialization = "objective:source_backed_decoder_target_materialization"
    target_store = "artifact:source_backed_decoder_target_store"
    audit_node = "audit:source_backed_decoder_target_materialization"
    dedup_gate = "gate:bounded_decoder_ce_split_dedup_required"
    added_nodes += int(add_node(nodes, {
        "id": materialization,
        "kind": "objective",
        "node_type": "objective",
        "name": "source_backed_decoder_target_materialization",
        "status": "target_store_materialized_ce_still_closed",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "rows": am.get("rows"),
        "materialized_rows": am.get("materialized_rows"),
        "blocked_rows": am.get("blocked_rows"),
        "decoder_ce_eligible_now_rows": am.get("decoder_ce_eligible_now_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": target_store,
        "kind": "artifact",
        "node_type": "artifact",
        "name": "source_backed_decoder_target_store",
        "status": "separate_target_store_not_model_input",
        "path": controls.get("artifacts", {}).get("target_store"),
        "target_store_rows": am.get("target_store_rows"),
        "target_text_copied_to_manifest_rows": am.get("target_text_copied_to_manifest_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": audit_node,
        "kind": "audit",
        "node_type": "audit",
        "name": "source_backed_decoder_target_materialization_audit",
        "status": "passed_leakage_authority_audit_ce_closed",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "cross_split_duplicate_target_hashes": am.get("cross_split_duplicate_target_hashes"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": dedup_gate,
        "kind": "gate",
        "node_type": "gate",
        "name": "bounded_decoder_ce_split_dedup_required",
        "status": "blocks_future_decoder_ce_loss_mask_selection",
        "reason": "target hashes repeat across train/eval/strict; future CE package must dedupe or rematerialize split-specific targets before any CE loss mask can open",
        "authority": AUTHORITY_CLOSED,
    }))
    for node_id in [
        "objective:bounded_decoder_ce",
        "objective:bounded_decoder_arguments",
        "support_module:dataset_junk_ood_ranker_v1",
        "support_module:contamination_leakage_detector",
        "support_module:curriculum_compiler",
        "support_module:cluster_slice_near_duplicate_detector",
        "support_module:golden_locked_eval_suite",
    ]:
        add_node(nodes, {"id": node_id, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
    add_edge(edges, "objective:bounded_decoder_ce", "requires_before_reopen", materialization)
    add_edge(edges, materialization, "writes_separate_target_store", target_store)
    add_edge(edges, audit_node, "audits", materialization)
    add_edge(edges, audit_node, "detects_future_ce_blocker", dedup_gate)
    add_edge(edges, dedup_gate, "blocks_loss_mask_open_for", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:contamination_leakage_detector", "must_validate", materialization)
    add_edge(edges, "support_module:dataset_junk_ood_ranker_v1", "must_route_before_training", materialization)
    add_edge(edges, "support_module:cluster_slice_near_duplicate_detector", "must_dedup_before_ce", dedup_gate)
    add_edge(edges, "support_module:golden_locked_eval_suite", "must_guard_split_boundary_for", dedup_gate)
    add_edge(edges, materialization, "precedes_closed_split_deduped_ce_candidate_selection", "objective:bounded_decoder_ce")
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_source_backed_decoder_target_materialization.json"
    nodes_path = OUT_DIR / "central_research_graph_with_source_backed_decoder_target_materialization_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_source_backed_decoder_target_materialization_edges.jsonl"
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
        "rows": am.get("rows"),
        "materialized_rows": am.get("materialized_rows"),
        "target_store_rows": am.get("target_store_rows"),
        "blocked_rows": am.get("blocked_rows"),
        "decoder_ce_eligible_now_rows": am.get("decoder_ce_eligible_now_rows"),
        "cross_split_duplicate_target_hashes": am.get("cross_split_duplicate_target_hashes"),
        "target_text_copied_to_manifest_rows": am.get("target_text_copied_to_manifest_rows"),
        "training_loss_rows": am.get("training_loss_rows"),
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
            "controls_summary": str(SOURCES[0].relative_to(ROOT)),
            "audit_summary": str(SOURCES[1].relative_to(ROOT)),
        },
        "decision": "Attached source-backed decoder target materialization to the central graph; decoder CE remains blocked by split-dedup and explicit authorization." if not failures else "Source-backed decoder target materialization graph attachment failed.",
        "next_best_step": "Build split-deduped closed CE candidate selection from the target store. Do not enable decoder CE/runtime.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "source_backed_decoder_target_materialization_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8808 Source-Backed Decoder Target Materialization Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Materialized rows: `{metrics['materialized_rows']}`",
        f"Target-store rows: `{metrics['target_store_rows']}`",
        f"CE eligible now rows: `{metrics['decoder_ce_eligible_now_rows']}`",
        f"Cross-split duplicate target hashes: `{metrics['cross_split_duplicate_target_hashes']}`",
        "",
        "The central graph now records target materialization as recovered but still CE-closed. Future CE candidate selection is blocked until split-dedup is handled.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
