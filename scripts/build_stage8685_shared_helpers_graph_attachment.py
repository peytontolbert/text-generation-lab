#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8683_recovered_support_modules_graph_attachment/central_research_graph_with_recovered_support_modules.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8685_shared_helpers_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8685_shared_helpers_graph_attachment.json"
DOC = ROOT / "docs/SHARED_HELPERS_GRAPH_ATTACHMENT_STAGE8685.md"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
AUTHORITY_CLOSED = {
    "model_execution_authorized_next": False,
    "decoder_ce_training_authorized_next": False,
    "runtime_authorized": False,
    "source_emission_authorized": False,
    "body_emission_authorized": False,
    "gemma_execution_authorized_next": False,
    "harness_execution_authorized_next": False,
    "scoring_authorized_next": False,
    "controller_complete_merge_authorized_next": False,
    "promotion_ready": False,
}


def has_node(nodes: list[dict[str, Any]], node_id: str) -> bool:
    return any(node.get("id") == node_id for node in nodes)


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> bool:
    if has_node(nodes, node["id"]):
        return False
    nodes.append(node)
    return True


def has_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    return any(edge.get("source") == source and edge.get("relation") == relation and edge.get("target") == target for edge in edges)


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str) -> bool:
    if has_edge(edges, source, relation, target):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": "stage8685_shared_helpers_graph_attachment"})
    return True


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text())
    nodes = list(graph["nodes"])
    edges = list(graph["edges"])
    added_nodes = 0
    added_edges = 0
    failures: list[str] = []
    summary_path = ROOT / "runs/summaries/stage8684_shared_helper_readiness.json"
    if not summary_path.exists():
        failures.append("missing_stage8684_summary")
        stage8684 = {}
    else:
        stage8684 = json.loads(summary_path.read_text())
        if stage8684.get("passed") is not True:
            failures.append("stage8684_not_passed")

    root = "control_execution_frontier:stage8685_shared_helpers"
    if add_node(nodes, {"id": root, "kind": "control_execution_frontier", "name": "stage8685_shared_helpers", "role": "shared feature/source guard helper recovery", "authority": AUTHORITY_CLOSED}):
        added_nodes += 1
    exec_node = "control_execution:stage8684_shared_helper_readiness"
    if add_node(nodes, {"id": exec_node, "kind": "control_execution", "name": "stage8684_shared_helper_readiness", "passed": stage8684.get("passed"), "metrics": stage8684.get("metrics", {}), "summary": "runs/summaries/stage8684_shared_helper_readiness.json", "authority": AUTHORITY_CLOSED}):
        added_nodes += 1
    if add_edge(edges, root, "contains_control_execution", exec_node):
        added_edges += 1
    for target in ["support_module:shared_feature_normalizer", "support_module:source_lineage_guard", "control_card:locked_eval:eval_split_policy", "control_card:leakage:split_contamination"]:
        if not has_node(nodes, target):
            if add_node(nodes, {"id": target, "kind": "support_module_or_control_card", "name": target.split(":", 1)[-1], "recovered_from": "stage8685_shared_helpers_graph_attachment"}):
                added_nodes += 1
        if add_edge(edges, exec_node, "recovers_or_enforces", target):
            added_edges += 1

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = "stage8685_shared_helpers_attached"
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED
    full = OUT_DIR / "central_research_graph_with_shared_helpers.json"
    nodes_jsonl = OUT_DIR / "central_research_graph_with_shared_helpers_nodes.jsonl"
    edges_jsonl = OUT_DIR / "central_research_graph_with_shared_helpers_edges.jsonl"
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
    nodes_jsonl.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes))
    edges_jsonl.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges))

    card = {
        "stage": 8685,
        "stage_name": "stage8685_shared_helpers_graph_attachment",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {"failures": failures, "added_nodes": added_nodes, "added_edges": added_edges, "graph_nodes": len(nodes), "graph_edges": len(edges), "model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "promotion_ready": False, "data_mining_allowed": False, "training_allowed": False},
        "artifacts": {"graph": str(full.relative_to(ROOT)), "nodes_jsonl": str(nodes_jsonl.relative_to(ROOT)), "edges_jsonl": str(edges_jsonl.relative_to(ROOT))},
        "decision": "Attached shared feature-normalizer and source-lineage/locked-eval guard helpers to the central graph. Mining and training remain closed.",
        "next_best_step": "Rerun recovered module/submodule readiness audit to update remaining gaps after Stage8681-8685 recovery.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "shared_helpers_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(f"# Stage8685 Shared Helpers Graph Attachment\n\nPassed: `{card['passed']}`\n\n- Graph nodes: `{len(nodes)}`\n- Graph edges: `{len(edges)}`\n- Failures: `{failures}`\n\nMining and training remain closed.\n")

    old_rows = []
    if REGISTRY.exists():
        try:
            old_rows = list((json.loads(REGISTRY.read_text()).get("rows") or []))
        except Exception:
            old_rows = []
    rows = old_rows + [card]
    REGISTRY.write_text(json.dumps({"passed": card["passed"], "rows": rows, "metrics": {"min_stage": min([row.get("stage", 8685) for row in rows] + [8685]), "max_stage": 8685, "latest_stage": 8685, "latest_stage_name": card["stage_name"], "latest_stage_next_best_step": card["next_best_step"], "registry_rows": len(rows), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}}, indent=2, sort_keys=True) + "\n")
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if card["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
