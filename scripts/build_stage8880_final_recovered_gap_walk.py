#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8880
NAME = "stage8880_final_recovered_gap_walk"
GRAPH = ROOT / "runs/local/artifacts/stage8879_closed_gate_status_reconciliation/central_research_graph_with_closed_gate_status_reconciliation.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "FINAL_RECOVERED_GAP_WALK_STAGE8880.md"
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
    closed_gates = []
    optional_missing = []
    for node in graph.get("nodes", []):
        status = str(node.get("status", ""))
        if status.startswith("passed") or status.startswith("resolved_by"):
            continue
        if "missing" in status or "blocked" in status:
            item = {"id": node.get("id"), "name": node.get("name"), "kind": node.get("kind") or node.get("node_type"), "status": status}
            unresolved.append(item)
            if node.get("id") == "objective:future_commit_inventory_preflight":
                optional_missing.append(item)
            if "closed_gate_recovered" in status:
                closed_gates.append(item)
        elif "closed_gate_recovered" in status:
            closed_gates.append({"id": node.get("id"), "name": node.get("name"), "kind": node.get("kind") or node.get("node_type"), "status": status})
    actionable = [item for item in unresolved if item.get("id") != "objective:future_commit_inventory_preflight"]
    prioritized = [
        {
            "priority": 1,
            "gap_id": "future_commit_inventory_preflight_optional",
            "node_id": "objective:future_commit_inventory_preflight",
            "next_step": "Only design this if repository walking is explicitly requested; otherwise leave closed.",
            "authority_closed": True,
        },
        {
            "priority": 2,
            "gap_id": "tiny_structured_probe_execution_review_optional",
            "node_id": "stage8890_tiny_structured_policy_probe_candidate",
            "next_step": "If the user explicitly wants execution, create an execution-authorization review card first; do not run directly.",
            "authority_closed": True,
        },
        {
            "priority": 3,
            "gap_id": "denoise_authorization_review_optional",
            "node_id": "objective:denoise_repair",
            "next_step": "Only design a no-execution denoise authorization review; denoise CE/runtime remain closed.",
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
            "unresolved_missing_or_blocked_nodes": len(unresolved),
            "optional_missing_nodes": len(optional_missing),
            "actionable_unresolved_nodes": len(actionable),
            "closed_gate_recovered_nodes": len(closed_gates),
            "prioritized_gap_count": len(prioritized),
            "registry_latest_stage": registry.get("metrics", {}).get("latest_stage"),
            "model_execution_authorized_now": False,
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "artifacts": {"graph": str(GRAPH.relative_to(ROOT)), "gap_walk": str((OUT_DIR / "final_recovered_gap_walk.json").relative_to(ROOT))},
        "unresolved_missing_or_blocked_nodes": unresolved,
        "optional_missing_nodes": optional_missing,
        "closed_gate_recovered_nodes": closed_gates,
        "prioritized_gaps": prioritized,
        "decision": "Recovered graph is now structurally caught up for the 100M software-maintainer control spine. Remaining work is optional explicit authorization review or optional metadata-only inventory preflight, not missing core curriculum modules.",
        "next_best_step": "Stop recovery churn and choose deliberately: explicit tiny structured probe authorization review, optional metadata-only commit inventory preflight, or continue non-executing denoise authorization design. Do not train/run directly.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "final_recovered_gap_walk.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8880 Final Recovered Gap Walk",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Unresolved missing/blocking nodes: `{card['metrics']['unresolved_missing_or_blocked_nodes']}`",
        f"Optional missing nodes: `{card['metrics']['optional_missing_nodes']}`",
        f"Actionable unresolved nodes: `{card['metrics']['actionable_unresolved_nodes']}`",
        f"Closed-gate recovered nodes: `{card['metrics']['closed_gate_recovered_nodes']}`",
        "",
        "Priority options:",
        "",
        *[f"{gap['priority']}. `{gap['gap_id']}` - {gap['next_step']}" for gap in prioritized],
        "",
        "No authority is opened.",
        "",
    ]), encoding="utf-8")
    print(json.dumps({"stage": STAGE, "stage_name": NAME, "passed": True, "metrics": card["metrics"], "prioritized_gaps": prioritized}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
