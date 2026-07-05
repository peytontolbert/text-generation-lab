#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8761
NAME = "stage8761_eval_trace_to_dataset_patch_loop_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8759_patch_coverage_flaky_graph_attachment/central_research_graph_with_patch_coverage_flaky.json"
SOURCE = ROOT / "runs/summaries/stage8760_eval_trace_to_dataset_patch_loop_readiness.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "EVAL_TRACE_TO_DATASET_PATCH_LOOP_GRAPH_ATTACHMENT_STAGE8761.md"
AUTHORITY_CLOSED = {"model_execution_authorized_next": False, "decoder_ce_training_authorized_next": False, "denoise_ce_training_authorized_next": False, "runtime_authorized": False, "source_emission_authorized": False, "body_emission_authorized": False, "gemma_execution_authorized_next": False, "harness_execution_authorized_next": False, "scoring_authorized_next": False, "controller_complete_merge_authorized_next": False, "promotion_ready": False}


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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    module = "support_module:eval_trace_to_dataset_patch_loop"
    added_nodes = int(add_node(nodes, {"id": module, "kind": "support_module", "node_type": "support_module", "name": "eval_trace_to_dataset_patch_loop", "status": "ready_partial_failure_to_curriculum_contract", "summary": str(SOURCE.relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    actions = ["ADD_COUNTERFACTUAL_NEIGHBOR", "ADD_RETRIEVAL_NEGATIVE", "ADD_BOUNDARY_POSITIVE", "ADD_BOUNDARY_NEGATIVE", "RELABEL_OR_REVIEW", "DOWNWEIGHT_OR_PRUNE", "HOLDOUT_LONG_OUTPUT", "ADD_VERIFIER_REPAIR_ROW", "REQUEST_SOURCE_EVIDENCE"]
    for action in actions:
        node_id = f"dataset_patch_action:{action}"
        added_nodes += int(add_node(nodes, {"id": node_id, "kind": "dataset_patch_action", "node_type": "dataset_patch_action", "status": "patch_action", "authority": AUTHORITY_CLOSED}))
        add_edge(edges, module, "may_emit_action", node_id)
    for upstream in ["support_module:training_data_attribution_influence", "support_module:dataset_cartography_active_learning", "support_module:drift_canary_regression_monitor", "support_module:contamination_leakage_detector"]:
        add_node(nodes, {"id": upstream, "kind": "support_module", "node_type": "support_module", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", module)
    for downstream in ["support_module:curriculum_compiler", "support_module:dataset_junk_ood_ranker_v1", "support_module:adversarial_hard_negative_generator", "objective:symbol_binding", "objective:edit_localization", "objective:patch_operator", "objective:verifier_repair", "objective:bounded_decoder_ce"]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, module, "emits_patch_for", downstream)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_eval_trace_to_dataset_patch_loop.json"
    nodes_path = OUT_DIR / "central_research_graph_with_eval_trace_to_dataset_patch_loop_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_eval_trace_to_dataset_patch_loop_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": STAGE, "stage_name": NAME, "passed": bool(source.get("passed")), "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "actions_attached": len(actions), "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added_nodes}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))}, "decision": "Attached eval_trace_to_dataset_patch_loop to central graph. Eval failures now have explicit dataset patch actions before new mining/training rows are created.", "next_best_step": "Update source-backed builders to emit full gate_status cards and run a no-training scale-readiness preflight.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "eval_trace_to_dataset_patch_loop_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8761 Eval Trace To Dataset Patch Loop Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached failure-to-curriculum dataset patch actions to the central graph.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))

if __name__ == "__main__":
    main()
