#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8793
NAME = "stage8793_query_recovery_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8790_source_backed_verifier_repair_graph_attachment/central_research_graph_with_source_backed_verifier_repair.json"
SOURCES = [
    ROOT / "runs/summaries/stage8791_query_expansion_rewriter_readiness.json",
    ROOT / "runs/summaries/stage8792_parallel_recovery_readiness_audit.json",
]
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "QUERY_RECOVERY_GRAPH_ATTACHMENT_STAGE8793.md"
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
    edge = {
        "src": src,
        "edge_type": relation,
        "dst": dst,
        "source": src,
        "relation": relation,
        "target": dst,
        "evidence_source": NAME,
    }
    if edge not in edges:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = json.loads(BASE.read_text(encoding="utf-8"))
    summaries = [json.loads(path.read_text(encoding="utf-8")) for path in SOURCES]
    failures = [summary.get("stage_name", str(index)) for index, summary in enumerate(summaries) if summary.get("passed") is not True]
    recovery_audit = summaries[1]
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))

    query = "support_module:query_expansion_rewriter"
    audit_node = "audit:parallel_recovery_readiness"
    added_nodes = 0
    added_nodes += int(add_node(nodes, {
        "id": query,
        "kind": "support_module",
        "node_type": "support_module",
        "name": "query_expansion_rewriter",
        "status": "ready_no_authority_shortcut_safe_query_expansion",
        "summary": str(SOURCES[0].relative_to(ROOT)),
        "outputs": ["query_variants", "query_source_bits", "expansion_reason"],
        "leakage_boundary": "blocks target_label, clean_state, target, answer, patch_operator, and other target-coded fields",
        "authority": AUTHORITY_CLOSED,
    }))
    added_nodes += int(add_node(nodes, {
        "id": audit_node,
        "kind": "audit",
        "node_type": "audit",
        "name": "parallel_recovery_readiness_audit",
        "status": "passed_all_stage8753_missing_real_modules_recovered",
        "summary": str(SOURCES[1].relative_to(ROOT)),
        "audited_missing_real_modules": recovery_audit.get("metrics", {}).get("audited_missing_real_modules"),
        "ready_local_modules": recovery_audit.get("metrics", {}).get("ready_local_modules"),
        "authority": AUTHORITY_CLOSED,
    }))

    for downstream in [
        "architecture_layer:evidence_retrieval",
        "support_module:hybrid_retrieval_fusion",
        "support_module:context_window_packer",
        "support_module:curriculum_compiler",
        "objective:source_backed_symbol_binding",
        "objective:source_backed_edit_localization",
        "objective:source_backed_patch_operator",
        "objective:source_backed_verifier_repair",
    ]:
        add_node(nodes, {"id": downstream, "kind": "support_or_objective", "node_type": "support_or_objective", "authority": AUTHORITY_CLOSED})
        add_edge(edges, query, "provides_shortcut_safe_query_variants_for", downstream)
    add_edge(edges, audit_node, "confirms_recovered", query)
    add_edge(edges, audit_node, "blocks_resume_until_reconciled_with", "support_module:curriculum_compiler")
    add_edge(edges, audit_node, "blocks_resume_until_reconciled_with", "support_module:stage_registry")
    add_edge(edges, audit_node, "blocks_resume_until_reconciled_with", "support_module:central_research_spine")

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_query_recovery.json"
    nodes_path = OUT_DIR / "central_research_graph_with_query_recovery_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_query_recovery_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")

    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "graph_nodes": len(out["nodes"]),
            "graph_edges": len(out["edges"]),
            "added_nodes": added_nodes,
            "audited_missing_real_modules": recovery_audit.get("metrics", {}).get("audited_missing_real_modules"),
            "ready_local_modules": recovery_audit.get("metrics", {}).get("ready_local_modules"),
        },
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
        },
        "decision": (
            "Attached query expansion readiness and parallel recovery completion audit to the central graph with all authorities closed."
            if not failures
            else "Query/recovery graph attachment failed."
        ),
        "next_best_step": "Run support-stack integration audit against the new graph, then reconcile registry/spine in one pass.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "query_recovery_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8793 Query Recovery Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Attached Stage8791 query-expansion readiness and Stage8792 parallel recovery completion audit to the latest central graph.",
        "",
        "The query rewriter is no-authority and blocks target-coded fields from query variants. The recovery audit confirms all Stage8753 missing-real support modules now have local files and readiness summaries.",
        "",
        "Authority remains closed: no mining, training, runtime, decoder CE, denoise CE, scoring, source/body emission, Gemma, controller merge, or promotion is authorized.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
