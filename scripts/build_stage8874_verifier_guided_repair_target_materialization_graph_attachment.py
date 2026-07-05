#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8874
NAME = "stage8874_verifier_guided_repair_target_materialization_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8869_stale_graph_status_reconciliation/central_research_graph_with_stale_status_reconciliation.json"
SUMMARY_8872 = ROOT / "runs/summaries/stage8872_verifier_guided_repair_target_materialization_controls.json"
SUMMARY_8873 = ROOT / "runs/summaries/stage8873_verifier_guided_repair_target_materialization_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "VERIFIER_GUIDED_REPAIR_TARGET_MATERIALIZATION_GRAPH_ATTACHMENT_STAGE8874.md"
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


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add_node(nodes: list[dict[str, Any]], node: dict[str, Any]) -> None:
    ids = {n.get("id") for n in nodes}
    if node["id"] not in ids:
        nodes.append(node)


def add_edge(edges: list[dict[str, Any]], edge: dict[str, Any]) -> None:
    key = (edge.get("source"), edge.get("relation"), edge.get("target"))
    if key not in {(e.get("source"), e.get("relation"), e.get("target")) for e in edges}:
        edges.append(edge)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(BASE)
    s8872 = load(SUMMARY_8872)
    s8873 = load(SUMMARY_8873)
    failures = []
    for src in [s8872, s8873]:
        if src.get("passed") is not True:
            failures.append(f"failed_source:{src.get('stage_name')}")
    nodes = list(graph.get("nodes", []))
    edges = list(graph.get("edges", []))
    by_id = {node.get("id"): node for node in nodes}
    target_node = by_id.get("objective:verifier_guided_repair_target_materialization")
    if target_node:
        target_node["previous_status"] = target_node.get("status")
        target_node["status"] = "resolved_by_stage8872_8873_controls_audit"
        target_node["resolved_by_stage"] = s8873.get("stage_name")
        target_node["authority"] = AUTHORITY_CLOSED
    else:
        failures.append("missing_graph_node:objective:verifier_guided_repair_target_materialization")
    add_node(nodes, {
        "id": "stage:8872",
        "kind": "stage",
        "name": "8872",
        "stage_name": s8872.get("stage_name"),
        "passed": s8872.get("passed"),
        "path": str(SUMMARY_8872.relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    })
    add_node(nodes, {
        "id": "stage:8873",
        "kind": "stage",
        "name": "8873",
        "stage_name": s8873.get("stage_name"),
        "passed": s8873.get("passed"),
        "path": str(SUMMARY_8873.relative_to(ROOT)),
        "authority": AUTHORITY_CLOSED,
    })
    add_node(nodes, {
        "id": "artifact:verifier_guided_repair_target_store",
        "kind": "artifact",
        "name": "verifier_guided_repair_target_store",
        "path": s8872.get("artifacts", {}).get("target_store"),
        "status": "target_store_only_not_model_input",
        "authority": AUTHORITY_CLOSED,
    })
    add_edge(edges, {"source": "objective_family:verifier_repair", "relation": "feeds", "target": "objective:verifier_guided_repair_target_materialization", "evidence_source": NAME})
    add_edge(edges, {"source": "objective:verifier_guided_repair_target_materialization", "relation": "implemented_by", "target": "stage:8872", "evidence_source": NAME})
    add_edge(edges, {"source": "stage:8872", "relation": "audited_by", "target": "stage:8873", "evidence_source": NAME})
    add_edge(edges, {"source": "stage:8872", "relation": "produces", "target": "artifact:verifier_guided_repair_target_store", "evidence_source": NAME})
    add_edge(edges, {"source": "artifact:verifier_guided_repair_target_store", "relation": "future_input_to", "target": "objective:denoise_repair", "evidence_source": NAME, "authority_note": "denoise_ce_closed"})
    out = {"version": NAME, "nodes": nodes, "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_verifier_guided_repair_target_materialization.json"
    nodes_path = OUT_DIR / "central_research_graph_with_verifier_guided_repair_target_materialization_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_verifier_guided_repair_target_materialization_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in nodes), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in edges), encoding="utf-8")
    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "graph_nodes": len(nodes),
        "graph_edges": len(edges),
        "materialized_rows": s8872.get("metrics", {}).get("materialized_rows"),
        "target_store_rows": s8872.get("metrics", {}).get("target_store_rows"),
        "denoise_ce_eligible_now_rows": s8873.get("metrics", {}).get("denoise_ce_eligible_now_rows"),
        "runtime_verifier_execution_eligible_now_rows": s8873.get("metrics", {}).get("runtime_verifier_execution_eligible_now_rows"),
        "source_failures": failures,
        "training_authorized": False,
        "denoise_ce_authorized": False,
        "runtime_authorized_flag": False,
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
        },
        "decision": "Attached verifier-guided repair target materialization controls to the central graph while keeping denoise/runtime closed." if not failures else "Graph attachment failed.",
        "next_best_step": "Reconcile registry/spine, then continue with eval/strict unique target materialization or packet-schema blockers.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8874 Verifier-Guided Repair Target Materialization Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Materialized rows: `{metrics['materialized_rows']}`",
        f"Target-store rows: `{metrics['target_store_rows']}`",
        f"Denoise CE eligible now rows: `{metrics['denoise_ce_eligible_now_rows']}`",
        f"Runtime verifier execution eligible now rows: `{metrics['runtime_verifier_execution_eligible_now_rows']}`",
        "",
        "The central graph now records verifier-guided repair target materialization as resolved by closed-boundary target-store controls. Denoise CE and runtime verifier execution remain blocked.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
