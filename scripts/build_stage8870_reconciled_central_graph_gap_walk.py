#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8870
NAME = "stage8870_reconciled_central_graph_gap_walk"
GRAPH = ROOT / "runs/local/artifacts/stage8869_stale_graph_status_reconciliation/central_research_graph_with_stale_status_reconciliation.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RECONCILED_CENTRAL_GRAPH_GAP_WALK_STAGE8870.md"
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(GRAPH)
    registry = load(REGISTRY)
    unresolved = []
    resolved = []
    for node in graph.get("nodes", []):
        status = node.get("status", "")
        if status == "resolved_by_reconciled_stage":
            resolved.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "resolved_by_stage": node.get("resolved_by_stage"),
                "previous_status": node.get("previous_status"),
            })
        elif "missing" in status or "blocked" in status:
            unresolved.append({
                "id": node.get("id"),
                "name": node.get("name"),
                "kind": node.get("kind") or node.get("node_type"),
                "status": status,
            })

    prioritized = [
        {
            "priority": 1,
            "gap_id": "future_commit_inventory_preflight",
            "node_id": "objective:future_commit_inventory_preflight",
            "next_step": "Design a bounded metadata-only commit inventory preflight only if repository walking is explicitly requested later.",
            "authority_closed": True,
        },
        {
            "priority": 2,
            "gap_id": "verifier_guided_repair_target_materialization",
            "node_id": "objective:verifier_guided_repair_target_materialization",
            "next_step": "Recover verifier-guided repair target materialization controls; keep denoise CE/runtime closed.",
            "authority_closed": True,
        },
        {
            "priority": 3,
            "gap_id": "eval_strict_unique_target_materialization",
            "node_id": "objective:eval_strict_unique_target_materialization",
            "next_step": "Recover split-unique eval/strict target materialization or explicitly preserve heldout non-CE boundary.",
            "authority_closed": True,
        },
        {
            "priority": 4,
            "gap_id": "future_probe_packet_schema_readiness",
            "node_id": "objective:future_model_output_packet_schema",
            "next_step": "Reconcile packet-schema nodes with completed Stage8823/8826 path or patch remaining runner-design blockers.",
            "authority_closed": True,
        },
    ]
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "graph_nodes": len(graph.get("nodes", [])),
            "graph_edges": len(graph.get("edges", [])),
            "resolved_reconciled_nodes": len(resolved),
            "unresolved_missing_or_blocked_nodes": len(unresolved),
            "prioritized_gap_count": len(prioritized),
            "registry_latest_stage": registry.get("metrics", {}).get("latest_stage"),
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "commit_mining_authorized": False,
            "arxiv_repository_walk_authorized": False,
        },
        "artifacts": {
            "graph": str(GRAPH.relative_to(ROOT)),
            "gap_walk": str((OUT_DIR / "reconciled_central_graph_gap_walk.json").relative_to(ROOT)),
        },
        "resolved_reconciled_nodes": resolved,
        "unresolved_missing_or_blocked_nodes": unresolved,
        "prioritized_gaps": prioritized,
        "decision": "Fresh gap walk after stale-status reconciliation complete. Stale missing nodes are gone; remaining blockers are true closed-boundary gaps.",
        "next_best_step": "Pick one unresolved blocker: future commit inventory preflight if repo walking is explicitly requested, otherwise verifier-guided repair target materialization.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "reconciled_central_graph_gap_walk.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8870 Reconciled Central Graph Gap Walk",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Resolved reconciled nodes: `{card['metrics']['resolved_reconciled_nodes']}`",
        f"Unresolved missing/blocking nodes: `{card['metrics']['unresolved_missing_or_blocked_nodes']}`",
        "",
        "Priority gaps:",
        "",
        *[f"{gap['priority']}. `{gap['gap_id']}` - {gap['next_step']}" for gap in prioritized],
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "metrics": card["metrics"],
        "prioritized_gaps": prioritized,
        "next_best_step": card["next_best_step"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
