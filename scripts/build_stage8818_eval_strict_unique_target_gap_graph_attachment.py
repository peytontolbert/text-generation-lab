#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8818
NAME = "stage8818_eval_strict_unique_target_gap_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8812_split_deduped_closed_ce_candidate_graph_attachment/central_research_graph_with_split_deduped_closed_ce_candidate_selection.json"
SOURCE = ROOT / "runs/summaries/stage8817_eval_strict_unique_target_gap_manifest.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EVAL_STRICT_UNIQUE_TARGET_GAP_GRAPH_ATTACHMENT_STAGE8818.md"
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
    gap = "gap:bounded_decoder_eval_strict_unique_target_materialization"
    manifest_node = "manifest:eval_strict_unique_target_gap"
    added += int(add_node(nodes, {"id": gap, "kind": "gap", "node_type": "gap", "name": "bounded_decoder_eval_strict_unique_target_materialization", "status": "materialized_as_gap_manifest", "rows": m.get("rows"), "split_counts": m.get("split_counts"), "authority": AUTHORITY_CLOSED}))
    added += int(add_node(nodes, {"id": manifest_node, "kind": "manifest", "node_type": "manifest", "name": "eval_strict_unique_target_gap_manifest", "summary": str(SOURCE.relative_to(ROOT)), "rows": m.get("rows"), "authority": AUTHORITY_CLOSED}))
    add_edge(edges, manifest_node, "materializes_gap", gap)
    add_edge(edges, gap, "blocks_probe_ready_package_for", "objective:bounded_decoder_ce")
    add_edge(edges, gap, "requires_resolution", "objective:source_backed_decoder_target_materialization")
    add_edge(edges, "support_module:golden_locked_eval_suite", "must_guard", gap)
    add_edge(edges, "support_module:cluster_slice_near_duplicate_detector", "must_guard", gap)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_eval_strict_unique_target_gap.json"
    nodes_path = OUT_DIR / "central_research_graph_with_eval_strict_unique_target_gap_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_eval_strict_unique_target_gap_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added, "gap_rows": m.get("rows"), "eval_gap_rows": (m.get("split_counts") or {}).get("eval"), "strict_gap_rows": (m.get("split_counts") or {}).get("strict"), "loss_rows": m.get("loss_rows"), "decoder_ce_eligible_now_rows": m.get("decoder_ce_eligible_now_rows")}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": metrics, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT)), "gap_summary": str(SOURCE.relative_to(ROOT))}, "decision": "Attached eval/strict unique target gap to central graph; CE package remains blocked until resolved." if not failures else "Eval/strict target gap graph attachment failed.", "next_best_step": "Design split-unique eval/strict target materialization or heldout non-CE evaluation package.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "eval_strict_unique_target_gap_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8818 Eval/Strict Unique Target Gap Graph Attachment", "", f"Passed: `{card['passed']}`", "", f"Gap rows: `{metrics['gap_rows']}`", f"Eval gap rows: `{metrics['eval_gap_rows']}`", f"Strict gap rows: `{metrics['strict_gap_rows']}`", "", "The graph now records the eval/strict target uniqueness gap as the blocker for any probe-ready bounded decoder CE package.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
