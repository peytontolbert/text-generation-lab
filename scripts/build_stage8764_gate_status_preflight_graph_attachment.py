#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8764
NAME = "stage8764_gate_status_preflight_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8761_eval_trace_to_dataset_patch_loop_graph_attachment/central_research_graph_with_eval_trace_to_dataset_patch_loop.json"
SOURCES = [
    ROOT / "runs/summaries/stage8762_gate_status_contract_readiness.json",
    ROOT / "runs/summaries/stage8763_no_training_scale_readiness_preflight.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "GATE_STATUS_PREFLIGHT_GRAPH_ATTACHMENT_STAGE8764.md"
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
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    failures = [s.get("stage_name", str(i)) for i, s in enumerate(summaries) if s.get("passed") is not True]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    gate_module = "support_module:gate_status_contract"
    preflight = "audit:no_training_scale_readiness_preflight"
    added_nodes += int(add_node(nodes, {"id": gate_module, "kind": "support_module", "node_type": "support_module", "name": "gate_status_contract", "status": "ready_complete_recovered_gate_card_contract", "summary": str(SOURCES[0].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {"id": preflight, "kind": "audit", "node_type": "audit", "name": "no_training_scale_readiness_preflight", "status": "passed" if not failures else "failed", "summary": str(SOURCES[1].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    for builder in ["builder:source_backed_symbol_binding", "builder:source_backed_edit_localization", "builder:source_backed_patch_operator", "builder:source_backed_verifier_repair", "support_module:curriculum_compiler"]:
        add_node(nodes, {"id": builder, "kind": "builder_or_support", "node_type": "builder_or_support", "authority": AUTHORITY_CLOSED})
        add_edge(edges, gate_module, "provides_required_gate_card_for", builder)
        add_edge(edges, builder, "must_pass", preflight)
    for gate in ["source_inventory_lineage", "source_provenance", "contamination_leakage_detector", "golden_locked_eval_suite", "drift_canary_regression_monitor", "cluster_slice_near_duplicate_detector", "dataset_junk_ood_ranker_v1", "schema_drift_detector"]:
        gate_id = f"recovered_gate:{gate}"
        add_node(nodes, {"id": gate_id, "kind": "recovered_gate", "node_type": "recovered_gate", "name": gate, "authority": AUTHORITY_CLOSED})
        add_edge(edges, gate_id, "required_by", gate_module)
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_gate_status_preflight.json"
    nodes_path = OUT_DIR / "central_research_graph_with_gate_status_preflight_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_gate_status_preflight_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added_nodes},
        "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))},
        "decision": "Attached complete gate_status contract and no-training scale-readiness preflight to the central graph." if not failures else "Gate status preflight graph attachment failed.",
        "next_best_step": "Patch remaining source-backed builders to use gate_status_contract before mining; then recover source-backed edit localization builder.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "gate_status_preflight_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8764 Gate Status Preflight Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached the recovered gate-status contract and no-training scale-readiness compiler preflight to the central graph.",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
