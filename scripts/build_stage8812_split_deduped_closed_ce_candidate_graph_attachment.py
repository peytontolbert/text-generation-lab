#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8812
NAME = "stage8812_split_deduped_closed_ce_candidate_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8808_source_backed_decoder_target_materialization_graph_attachment/central_research_graph_with_source_backed_decoder_target_materialization.json"
SOURCES = [
    ROOT / "runs/summaries/stage8810_split_deduped_closed_ce_candidate_selection.json",
    ROOT / "runs/summaries/stage8811_split_deduped_closed_ce_candidate_selection_audit.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SPLIT_DEDUPED_CLOSED_CE_CANDIDATE_GRAPH_ATTACHMENT_STAGE8812.md"
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
    selection, audit = cards
    sm, am = selection.get("metrics", {}), audit.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    candidate = "objective:split_deduped_closed_bounded_decoder_ce_candidate_selection"
    audit_node = "audit:split_deduped_closed_bounded_decoder_ce_candidate_selection"
    eval_gap = "gap:bounded_decoder_eval_strict_unique_target_materialization"
    added_nodes += int(add_node(nodes, {
        "id": candidate,
        "kind": "objective",
        "node_type": "objective",
        "name": "split_deduped_closed_bounded_decoder_ce_candidate_selection",
        "status": "passed_train_only_candidate_support_not_probe_ready",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "selected_candidate_rows": am.get("selected_candidate_rows"),
        "selected_split_counts": am.get("selected_split_counts"),
        "probe_ready": am.get("probe_ready"),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": audit_node,
        "kind": "audit",
        "node_type": "audit",
        "name": "split_deduped_closed_ce_candidate_selection_audit",
        "status": "passed_ce_closed_train_only",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": eval_gap,
        "kind": "gap",
        "node_type": "gap",
        "name": "bounded_decoder_eval_strict_unique_target_materialization",
        "status": "missing_before_probe_ready_ce_package",
        "reason": "deduped target hashes leave selected CE candidates train-only; eval and strict need unique target materialization or heldout evaluation design",
        "authority": AUTHORITY_CLOSED,
    }))
    add_edge(edges, "objective:source_backed_decoder_target_materialization", "feeds", candidate)
    add_edge(edges, audit_node, "audits", candidate)
    add_edge(edges, candidate, "blocked_from_probe_by", eval_gap)
    add_edge(edges, eval_gap, "blocks_loss_mask_open_for", "objective:bounded_decoder_ce")
    add_edge(edges, "support_module:golden_locked_eval_suite", "must_guard", eval_gap)
    add_edge(edges, "support_module:cluster_slice_near_duplicate_detector", "must_guard", eval_gap)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_split_deduped_closed_ce_candidate_selection.json"
    nodes_path = OUT_DIR / "central_research_graph_with_split_deduped_closed_ce_candidate_selection_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_split_deduped_closed_ce_candidate_selection_edges.jsonl"
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
        "selected_candidate_rows": am.get("selected_candidate_rows"),
        "selected_eval_rows": am.get("selected_eval_rows"),
        "selected_strict_rows": am.get("selected_strict_rows"),
        "probe_ready": am.get("probe_ready"),
        "training_loss_rows": am.get("training_loss_rows"),
        "decoder_ce_eligible_now_rows": am.get("decoder_ce_eligible_now_rows"),
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
            "selection_summary": str(SOURCES[0].relative_to(ROOT)),
            "audit_summary": str(SOURCES[1].relative_to(ROOT)),
        },
        "decision": "Attached split-deduped closed CE selection to graph as train-only candidate support; CE probe remains blocked pending eval/strict unique target design." if not failures else "Split-deduped CE candidate graph attachment failed.",
        "next_best_step": "Recover eval/strict unique target materialization or heldout evaluation design before any CE loss-mask package.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "split_deduped_closed_ce_candidate_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8812 Split-Deduped Closed CE Candidate Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Selected candidate rows: `{metrics['selected_candidate_rows']}`",
        f"Probe ready: `{metrics['probe_ready']}`",
        "",
        "The central graph now records the safe train-only CE candidate set and the remaining eval/strict target materialization gap.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
