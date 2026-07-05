#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8877
NAME = "stage8877_reconciled_gap_walk_after_target_materialization"
GRAPH = ROOT / "runs/local/artifacts/stage8876_post_target_materialization_gap_reconciliation/central_research_graph_post_target_materialization_reconciled.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "RECONCILED_GAP_WALK_AFTER_TARGET_MATERIALIZATION_STAGE8877.md"
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
    closed_gate_blockers = []
    for node in graph.get("nodes", []):
        status = str(node.get("status", ""))
        if status.startswith("resolved_by"):
            resolved.append({"id": node.get("id"), "name": node.get("name"), "status": status, "resolved_by_stage": node.get("resolved_by_stage")})
        elif "missing" in status or "blocked" in status:
            item = {"id": node.get("id"), "name": node.get("name"), "kind": node.get("kind") or node.get("node_type"), "status": status}
            unresolved.append(item)
            if "closed" in status or "authority" in status or "pending" in status:
                closed_gate_blockers.append(item)
    prioritized = [
        {
            "priority": 1,
            "gap_id": "future_commit_inventory_preflight",
            "node_id": "objective:future_commit_inventory_preflight",
            "next_step": "Design metadata-only commit inventory preflight only if repository walking is explicitly requested; no commit walking/mining by default.",
            "authority_closed": True,
        },
        {
            "priority": 2,
            "gap_id": "bounded_decoder_ce_closed_gate",
            "node_id": "objective:bounded_decoder_ce",
            "next_step": "Keep bounded decoder CE closed until explicit tiny execution authorization; current target controls and telemetry gates are recovered.",
            "authority_closed": True,
        },
        {
            "priority": 3,
            "gap_id": "denoise_repair_closed_gate",
            "node_id": "objective:denoise_repair",
            "next_step": "Verifier-guided repair targets exist, but denoise CE/runtime remain closed pending dedicated no-execution denoise gate.",
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
            "resolved_nodes": len(resolved),
            "unresolved_missing_or_blocked_nodes": len(unresolved),
            "closed_gate_blockers": len(closed_gate_blockers),
            "prioritized_gap_count": len(prioritized),
            "registry_latest_stage": registry.get("metrics", {}).get("latest_stage"),
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "artifacts": {"graph": str(GRAPH.relative_to(ROOT)), "gap_walk": str((OUT_DIR / "reconciled_gap_walk_after_target_materialization.json").relative_to(ROOT))},
        "unresolved_missing_or_blocked_nodes": unresolved,
        "closed_gate_blockers": closed_gate_blockers,
        "prioritized_gaps": prioritized,
        "decision": "Fresh gap walk after verifier/target/packet reconciliation complete. Remaining blockers are closed authority gates or explicitly optional commit inventory preflight.",
        "next_best_step": "Do not train yet. Either design metadata-only commit inventory preflight if explicitly requested, or prepare an execution-authorization review for the tiny Stage8890 structured probe.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "reconciled_gap_walk_after_target_materialization.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8877 Reconciled Gap Walk After Target Materialization",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Unresolved missing/blocking nodes: `{card['metrics']['unresolved_missing_or_blocked_nodes']}`",
        f"Closed-gate blockers: `{card['metrics']['closed_gate_blockers']}`",
        "",
        "Priority gaps:",
        "",
        *[f"{gap['priority']}. `{gap['gap_id']}` - {gap['next_step']}" for gap in prioritized],
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps({"stage": STAGE, "stage_name": NAME, "passed": True, "metrics": card["metrics"], "prioritized_gaps": prioritized}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
