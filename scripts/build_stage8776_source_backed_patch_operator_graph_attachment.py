#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8776
NAME = "stage8776_source_backed_patch_operator_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8773_ngram_memory_graph_attachment/central_research_graph_with_ngram_memory.json"
SOURCES = [ROOT / "runs/summaries/stage8774_source_backed_patch_operator_candidate_manifest.json", ROOT / "runs/summaries/stage8775_source_backed_patch_operator_candidate_audit.json"]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "SOURCE_BACKED_PATCH_OPERATOR_GRAPH_ATTACHMENT_STAGE8776.md"
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
    audit = summaries[1]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added_nodes = 0
    builder = "builder:source_backed_patch_operator"
    audit_node = "audit:source_backed_patch_operator_candidate"
    objective = "objective:patch_operator"
    added_nodes += int(add_node(nodes, {"id": builder, "kind": "builder", "node_type": "builder", "name": "source_backed_patch_operator_builder", "status": "candidate_ready_no_training", "summary": str(SOURCES[0].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    added_nodes += int(add_node(nodes, {"id": audit_node, "kind": "audit", "node_type": "audit", "name": "source_backed_patch_operator_candidate_audit", "status": "passed_candidate_only" if not failures else "failed", "summary": str(SOURCES[1].relative_to(ROOT)), "authority": AUTHORITY_CLOSED}))
    add_node(nodes, {"id": objective, "kind": "objective", "node_type": "objective", "authority": AUTHORITY_CLOSED})
    for upstream in ["support_module:gate_status_contract", "support_module:source_inventory_lineage_tracker", "support_module:contamination_leakage_detector", "support_module:schema_drift_detector", "support_module:dataset_junk_ood_ranker_v1", "support_module:ngram_repetition_style_detectors", "objective:edit_localization"]:
        add_node(nodes, {"id": upstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, upstream, "feeds", builder)
    add_edge(edges, builder, "produces_candidate_for", objective)
    add_edge(edges, builder, "audited_by", audit_node)
    add_edge(edges, audit_node, "blocks_training_until_compiler_ready_gate_status", objective)
    add_edge(edges, audit_node, "next_recovery_target", "builder:source_backed_verifier_repair")
    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_source_backed_patch_operator.json"
    nodes_path = OUT_DIR / "central_research_graph_with_source_backed_patch_operator_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_source_backed_patch_operator_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "rows": audit["metrics"].get("rows"), "contamination_blocked_rows": audit["metrics"].get("contamination_blocked_rows"), "schema_blocked_rows": audit["metrics"].get("schema_blocked_rows"), "graph_nodes": len(out["nodes"]), "graph_edges": len(out["edges"]), "added_nodes": added_nodes}, "artifacts": {"graph": str(graph_path.relative_to(ROOT)), "nodes_jsonl": str(nodes_path.relative_to(ROOT)), "edges_jsonl": str(edges_path.relative_to(ROOT))}, "decision": "Attached source-backed patch-operator candidate builder/audit to the central graph. Rows remain candidate-only; no training or mining authority opened." if not failures else "Source-backed patch-operator graph attachment failed.", "next_best_step": "Recover source-backed verifier-repair builder under the same gate_status contract.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (OUT_DIR / "source_backed_patch_operator_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8776 Source-Backed Patch Operator Graph Attachment", "", f"Passed: `{card['passed']}`", "", "Attached source-backed patch operator as candidate-ready, no-training recovery work.", "", "Authority remains closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
