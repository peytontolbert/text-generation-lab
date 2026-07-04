#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8678_symbol_binding_repair_graph_attachment/central_research_graph_with_symbol_binding_repair.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8683_recovered_support_modules_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8683_recovered_support_modules_graph_attachment.json"
DOC = ROOT / "docs/RECOVERED_SUPPORT_MODULES_GRAPH_ATTACHMENT_STAGE8683.md"
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

STAGES = {
    "stage8681_unified_dataset_junk_ood_ranker_readiness": "runs/summaries/stage8681_unified_dataset_junk_ood_ranker_readiness.json",
    "stage8682_cluster_slice_detector_readiness": "runs/summaries/stage8682_cluster_slice_detector_readiness.json",
}

MODULE_TARGETS = {
    "stage8681_unified_dataset_junk_ood_ranker_readiness": [
        "support_module:junk_risk_ood_ranker",
        "support_module:structured_dataset_junk_ranker",
        "support_module:objective_row_judge",
        "support_module:loss_mask_cards",
    ],
    "stage8682_cluster_slice_detector_readiness": [
        "support_module:cluster_slice_detection",
        "support_module:dedup_near_duplicate_minhash",
        "support_module:contamination_leakage_detector",
    ],
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


def add_edge(edges: list[dict[str, Any]], source: str, relation: str, target: str, evidence: str) -> bool:
    if has_edge(edges, source, relation, target):
        return False
    edges.append({"source": source, "relation": relation, "target": target, "evidence_source": evidence})
    return True


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text())
    nodes = list(graph["nodes"])
    edges = list(graph["edges"])
    added_nodes = 0
    added_edges = 0
    failures: list[str] = []
    statuses: dict[str, dict[str, Any]] = {}

    root = "control_execution_frontier:stage8683_recovered_support_modules"
    if add_node(nodes, {"id": root, "kind": "control_execution_frontier", "name": "stage8683_recovered_support_modules", "role": "ranker and cluster detector executable support recovery", "authority": AUTHORITY_CLOSED}):
        added_nodes += 1

    for name, rel in STAGES.items():
        path = ROOT / rel
        if not path.exists():
            failures.append("missing_summary:" + rel)
            continue
        data = json.loads(path.read_text())
        statuses[name] = {"passed": data.get("passed"), "metrics": data.get("metrics", {}), "summary": rel}
        if data.get("passed") is not True:
            failures.append("control_not_passed:" + name)
        node_id = "control_execution:" + name
        if add_node(nodes, {"id": node_id, "kind": "control_execution", "name": name, "passed": data.get("passed"), "metrics": data.get("metrics", {}), "summary": rel, "authority": AUTHORITY_CLOSED, "recovered_from": "stage8683_recovered_support_modules_graph_attachment"}):
            added_nodes += 1
        if add_edge(edges, root, "contains_control_execution", node_id, "stage8683_recovered_support_modules_graph_attachment"):
            added_edges += 1
        for target in MODULE_TARGETS[name]:
            if not has_node(nodes, target):
                if add_node(nodes, {"id": target, "kind": "support_module", "name": target.split(":", 1)[-1], "recovered_from": "stage8683_recovered_support_modules_graph_attachment"}):
                    added_nodes += 1
            if add_edge(edges, node_id, "recovers_or_consolidates", target, "stage8683_recovered_support_modules_graph_attachment"):
                added_edges += 1

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = "stage8683_recovered_support_modules_attached"
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED
    full = OUT_DIR / "central_research_graph_with_recovered_support_modules.json"
    nodes_jsonl = OUT_DIR / "central_research_graph_with_recovered_support_modules_nodes.jsonl"
    edges_jsonl = OUT_DIR / "central_research_graph_with_recovered_support_modules_edges.jsonl"
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
    nodes_jsonl.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes))
    edges_jsonl.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges))

    card = {
        "stage": 8683,
        "stage_name": "stage8683_recovered_support_modules_graph_attachment",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "failures": failures,
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "control_execution_nodes": len(statuses),
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
            "data_mining_allowed": False,
            "training_allowed": False,
        },
        "statuses": statuses,
        "artifacts": {
            "graph": str(full.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_jsonl.relative_to(ROOT)),
            "edges_jsonl": str(edges_jsonl.relative_to(ROOT)),
        },
        "decision": "Attached the recovered unified ranker and cluster/slice detector support modules to the central graph. Mining and training remain closed.",
        "next_best_step": "Recover shared locked-eval/source-exclusion and shared feature-normalizer importable helper libraries, then rerun module readiness audit.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "recovered_support_modules_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8683 Recovered Support Modules Graph Attachment\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Added nodes: `{added_nodes}`\n"
        f"- Added edges: `{added_edges}`\n"
        f"- Graph nodes: `{len(nodes)}`\n"
        f"- Graph edges: `{len(edges)}`\n"
        f"- Failures: `{failures}`\n\n"
        "Mining, model execution, training, decoder CE, denoise CE, runtime, and promotion remain closed.\n"
    )

    old_rows = []
    if REGISTRY.exists():
        try:
            old_rows = list((json.loads(REGISTRY.read_text()).get("rows") or []))
        except Exception:
            old_rows = []
    rows = old_rows + [card]
    REGISTRY.write_text(
        json.dumps(
            {
                "passed": card["passed"],
                "rows": rows,
                "metrics": {
                    "min_stage": min([row.get("stage", 8683) for row in rows] + [8683]),
                    "max_stage": 8683,
                    "latest_stage": 8683,
                    "latest_stage_name": card["stage_name"],
                    "latest_stage_next_best_step": card["next_best_step"],
                    "registry_rows": len(rows),
                    "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    print(json.dumps(card, indent=2, sort_keys=True))
    return 0 if card["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
