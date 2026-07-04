#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "runs/local/artifacts/stage8673_retrieval_eval_controls_graph_attachment/central_research_graph_with_retrieval_eval_controls.json"
OUT_DIR = ROOT / "runs/local/artifacts/stage8678_symbol_binding_repair_graph_attachment"
SUMMARY = ROOT / "runs/summaries/stage8678_symbol_binding_repair_graph_attachment.json"
DOC = ROOT / "docs/SYMBOL_BINDING_REPAIR_GRAPH_ATTACHMENT_STAGE8678.md"
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

SUMMARIES = {
    "stage8674_source_backed_symbol_binding_candidate_manifest": "runs/summaries/stage8674_source_backed_symbol_binding_candidate_manifest.json",
    "stage8675_source_backed_symbol_binding_candidate_manifest_audit": "runs/summaries/stage8675_source_backed_symbol_binding_candidate_manifest_audit.json",
    "stage8676_source_backed_symbol_binding_shortcut_repair_manifest": "runs/summaries/stage8676_source_backed_symbol_binding_shortcut_repair_manifest.json",
    "stage8677_source_backed_symbol_binding_shortcut_repair_audit": "runs/summaries/stage8677_source_backed_symbol_binding_shortcut_repair_audit.json",
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

    root = "control_execution_frontier:stage8678_symbol_binding_repair"
    if add_node(
        nodes,
        {
            "id": root,
            "kind": "control_execution_frontier",
            "name": "stage8678_symbol_binding_repair",
            "role": "source-backed symbol-binding candidate plus shortcut repair audit frontier",
            "authority": AUTHORITY_CLOSED,
        },
    ):
        added_nodes += 1

    previous = None
    for stage_name, rel in SUMMARIES.items():
        path = ROOT / rel
        if not path.exists():
            failures.append("missing_summary:" + rel)
            continue
        data = json.loads(path.read_text())
        statuses[stage_name] = {"passed": data.get("passed"), "metrics": data.get("metrics", {}), "summary": rel}
        # Stage8675 is expected to fail and is preserved as evidence of the shortcut defect.
        if stage_name != "stage8675_source_backed_symbol_binding_candidate_manifest_audit" and data.get("passed") is not True:
            failures.append("control_not_passed:" + stage_name)
        if stage_name == "stage8675_source_backed_symbol_binding_candidate_manifest_audit" and data.get("passed") is not False:
            failures.append("expected_failure_not_preserved:" + stage_name)

        node_id = "control_execution:" + stage_name
        if add_node(
            nodes,
            {
                "id": node_id,
                "kind": "control_execution",
                "name": stage_name,
                "passed": data.get("passed"),
                "metrics": data.get("metrics", {}),
                "summary": rel,
                "authority": AUTHORITY_CLOSED,
                "recovered_from": "stage8678_symbol_binding_repair_graph_attachment",
            },
        ):
            added_nodes += 1
        if add_edge(edges, root, "contains_control_execution", node_id, "stage8678_symbol_binding_repair_graph_attachment"):
            added_edges += 1
        if previous and add_edge(edges, previous, "followed_by", node_id, "stage8678_symbol_binding_repair_graph_attachment"):
            added_edges += 1
        previous = node_id

    candidate = "control_execution:stage8674_source_backed_symbol_binding_candidate_manifest"
    failure = "control_execution:stage8675_source_backed_symbol_binding_candidate_manifest_audit"
    repair = "control_execution:stage8676_source_backed_symbol_binding_shortcut_repair_manifest"
    audit = "control_execution:stage8677_source_backed_symbol_binding_shortcut_repair_audit"
    for source, relation, target in [
        (candidate, "exposed_failure_in", failure),
        (failure, "repaired_by", repair),
        (repair, "validated_by", audit),
        (audit, "keeps_authority_closed_for", "control_card:leakage:shortcut_proxy_audit"),
        (audit, "uses_retrieval_control", "control_execution:stage8671_dense_hybrid_retrieval_baseline"),
        (audit, "uses_locked_eval_boundary", "control_execution:stage8672_locked_benchmark_pack_manifest"),
    ]:
        if not has_node(nodes, target):
            if add_node(nodes, {"id": target, "kind": "recovered_placeholder_target", "name": target.split(":", 1)[-1]}):
                added_nodes += 1
        if add_edge(edges, source, relation, target, "stage8678_symbol_binding_repair_graph_attachment"):
            added_edges += 1

    graph["nodes"] = nodes
    graph["edges"] = edges
    graph["version"] = "stage8678_symbol_binding_repair_attached"
    graph["generated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    graph["authority"] = AUTHORITY_CLOSED
    full = OUT_DIR / "central_research_graph_with_symbol_binding_repair.json"
    nodes_jsonl = OUT_DIR / "central_research_graph_with_symbol_binding_repair_nodes.jsonl"
    edges_jsonl = OUT_DIR / "central_research_graph_with_symbol_binding_repair_edges.jsonl"
    full.write_text(json.dumps(graph, indent=2, sort_keys=True) + "\n")
    nodes_jsonl.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes))
    edges_jsonl.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges))

    card = {
        "stage": 8678,
        "stage_name": "stage8678_symbol_binding_repair_graph_attachment",
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            "failures": failures,
            "added_nodes": added_nodes,
            "added_edges": added_edges,
            "graph_nodes": len(nodes),
            "graph_edges": len(edges),
            "control_execution_nodes": len(statuses),
            "expected_failed_stage_preserved": statuses.get("stage8675_source_backed_symbol_binding_candidate_manifest_audit", {}).get("passed") is False,
            "latest_validated_stage": 8677,
            "model_execution_authorized_next": False,
            "decoder_ce_training_authorized_next": False,
            "denoise_ce_training_authorized_next": False,
            "runtime_authorized": False,
            "promotion_ready": False,
        },
        "statuses": statuses,
        "artifacts": {
            "graph": str(full.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_jsonl.relative_to(ROOT)),
            "edges_jsonl": str(edges_jsonl.relative_to(ROOT)),
        },
        "decision": "Attached the source-backed symbol-binding shortcut failure and repair chain to the central graph; Stage8677 is the current validated candidate-only frontier.",
        "next_best_step": "Mine or generate more query_kind=test counterexamples before increasing row count or authorizing any finite-head training; keep decoder/runtime/body/Gemma closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "symbol_binding_repair_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n")
    DOC.write_text(
        "# Stage8678 Symbol Binding Repair Graph Attachment\n\n"
        f"Passed: `{card['passed']}`\n\n"
        f"- Added nodes: `{added_nodes}`\n"
        f"- Added edges: `{added_edges}`\n"
        f"- Graph nodes: `{len(nodes)}`\n"
        f"- Graph edges: `{len(edges)}`\n"
        f"- Expected failed Stage8675 preserved: `{card['metrics']['expected_failed_stage_preserved']}`\n"
        f"- Failures: `{failures}`\n\n"
        "All authorities remain closed.\n"
    )

    old_rows = []
    if REGISTRY.exists():
        try:
            old = json.loads(REGISTRY.read_text())
            old_rows = list(old.get("rows") or [])
        except Exception:
            old_rows = []
    rows_out = old_rows + [card]
    REGISTRY.write_text(
        json.dumps(
            {
                "passed": card["passed"],
                "rows": rows_out,
                "metrics": {
                    "min_stage": min([row.get("stage", 8678) for row in rows_out] + [8678]),
                    "max_stage": 8678,
                    "latest_stage": 8678,
                    "latest_stage_name": card["stage_name"],
                    "latest_stage_next_best_step": card["next_best_step"],
                    "registry_rows": len(rows_out),
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
