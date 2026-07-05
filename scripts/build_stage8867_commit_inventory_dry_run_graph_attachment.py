#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8867
NAME = "stage8867_commit_inventory_dry_run_graph_attachment"
BASE = ROOT / "runs/local/artifacts/stage8859_commit_learning_signal_graph_attachment/central_research_graph_with_commit_learning_signal_contract.json"
SOURCE = ROOT / "runs/summaries/stage8865_commit_inventory_dry_run_design.json"
AUDIT = ROOT / "runs/summaries/stage8866_commit_inventory_dry_run_gate_audit.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "COMMIT_INVENTORY_DRY_RUN_GRAPH_ATTACHMENT_STAGE8867.md"
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


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(BASE)
    src = load(SOURCE)
    audit = load(AUDIT)
    failures = []
    if src.get("passed") is not True:
        failures.append(src.get("stage_name"))
    if audit.get("passed") is not True:
        failures.append(audit.get("stage_name"))
    m = src.get("metrics", {})
    a = audit.get("metrics", {})
    nodes = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    edges = list(graph.get("edges", []))
    added = 0

    design = "design:commit_inventory_dry_run_v1"
    gate = "audit:commit_inventory_dry_run_gate"
    contract = "contract:commit_learning_signal_v1"
    next_preflight = "objective:future_commit_inventory_preflight"
    added += int(add_node(nodes, {
        "id": design,
        "kind": "design",
        "node_type": "design",
        "name": "commit_inventory_dry_run_v1",
        "status": "design_ready_zero_walk_zero_commit_read",
        "rows": m.get("rows"),
        "ready_rows": m.get("dry_run_design_ready_rows"),
        "inventory_fields": m.get("inventory_fields"),
        "commit_metadata_fields": m.get("commit_metadata_fields"),
        "caps_and_bounds": m.get("caps_and_bounds"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": gate,
        "kind": "audit",
        "node_type": "audit",
        "name": "commit_inventory_dry_run_gate",
        "status": "passed_zero_walk_zero_commit_read",
        "gate_pass_rows": a.get("gate_pass_rows"),
        "authority": AUTHORITY_CLOSED,
    }))
    added += int(add_node(nodes, {
        "id": next_preflight,
        "kind": "objective",
        "node_type": "objective",
        "name": "future_commit_inventory_preflight",
        "status": "missing_next_recovery_target",
        "purpose": "Future preflight may authorize a bounded metadata-only inventory pass, but this stage does not.",
        "authority": AUTHORITY_CLOSED,
    }))
    for gate_node in [
        "gate:source_inventory_lineage",
        "gate:source_provenance",
        "gate:contamination_leakage_detector",
        "gate:golden_locked_eval_suite",
        "gate:dataset_junk_ood_ranker_v1",
        "gate:cluster_slice_near_duplicate_detector",
    ]:
        add_node(nodes, {"id": gate_node, "kind": "support_or_gate", "node_type": "support_or_gate", "authority": AUTHORITY_CLOSED})
        add_edge(edges, design, "requires_source_gate_before_future_inventory", gate_node)
    add_edge(edges, contract, "requires_inventory_design_before_future_mining", design)
    add_edge(edges, design, "audited_by", gate)
    add_edge(edges, gate, "required_before", next_preflight)

    out = {"version": NAME, "nodes": list(nodes.values()), "edges": edges}
    graph_path = OUT_DIR / "central_research_graph_with_commit_inventory_dry_run.json"
    nodes_path = OUT_DIR / "central_research_graph_with_commit_inventory_dry_run_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_commit_inventory_dry_run_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "source_failures": failures,
        "graph_nodes": len(out["nodes"]),
        "graph_edges": len(out["edges"]),
        "added_nodes": added,
        "dry_run_design_rows": m.get("rows"),
        "gate_pass_rows": a.get("gate_pass_rows"),
        "arxiv_repository_walk_authorized": False,
        "commit_reads_authorized": False,
        "commit_mining_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
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
            "design_summary": str(SOURCE.relative_to(ROOT)),
            "gate_summary": str(AUDIT.relative_to(ROOT)),
        },
        "decision": "Attached dry-run commit inventory design to graph. Future inventory preflight remains missing; repository walking remains closed.",
        "next_best_step": "Reconcile registry/spine, then recover stale graph status reconciliation or future commit inventory preflight. Keep repository walking, training, and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "commit_inventory_dry_run_graph_attachment_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8867 Commit Inventory Dry-Run Graph Attachment",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Design rows: `{metrics['dry_run_design_rows']}`",
        f"Gate pass rows: `{metrics['gate_pass_rows']}`",
        f"/arxiv repository walk authorized: `{metrics['arxiv_repository_walk_authorized']}`",
        f"Commit reads authorized: `{metrics['commit_reads_authorized']}`",
        f"Training authorized: `{metrics['training_authorized']}`",
        f"Decoder CE authorized: `{metrics['decoder_ce_authorized']}`",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
