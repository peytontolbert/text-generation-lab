#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8863
NAME = "stage8863_central_graph_gap_walk"
GRAPH = ROOT / "runs/local/artifacts/stage8859_commit_learning_signal_graph_attachment/central_research_graph_with_commit_learning_signal_contract.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
DOC = ROOT / "docs" / "CENTRAL_GRAPH_GAP_WALK_STAGE8863.md"

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

RESOLUTION_HINTS = {
    "objective:learning_signal_dataset_trainer_implementation_plan": "stage8847_learning_signal_implementation_plan",
    "objective:learning_signal_implementation_plan_gate_audit": "stage8849_learning_signal_implementation_plan_gate_audit",
    "objective:learning_signal_code_patch_readiness_gate_audit": "stage8853_learning_signal_code_patch_readiness_gate_audit",
    "objective:commit_learning_signal_no_mining_gate_audit": "stage8860_commit_learning_signal_no_mining_gate_audit",
    "objective:future_model_output_capture_authority_ticket_schema": "stage8840_authority_ticket_schema",
    "objective:authority_ticket_schema_gate_audit": "stage8842_authority_ticket_schema_gate_audit",
    "objective:model_output_capture_preflight_audit": "stage8834_model_output_capture_preflight_design_audit",
    "objective:future_model_output_capture_runner_static_design": "stage8837_model_output_capture_runner_static_design",
}

TRUE_GAPS = [
    {
        "gap_id": "commit_inventory_dry_run_design",
        "priority": 1,
        "why": "Needed before walking /arxiv/repositories. It should define inventory fields, caps, and safety checks without reading commits yet.",
        "next_step": "Recover dry-run commit inventory design. Keep repository walking, training, and decoder CE closed.",
        "blocked_authority": ["arxiv_repository_walk", "commit_mining", "training", "decoder_ce"],
    },
    {
        "gap_id": "native_probe_interpretability_artifact_gate_application",
        "priority": 2,
        "why": "Stage8862 defines the artifact contract, but the first real tiny probe output still needs to be checked by the contract before interpreting metrics.",
        "next_step": "Only after explicit probe authorization, run artifact contract against the tiny probe output; otherwise keep as closed contract.",
        "blocked_authority": ["model_execution"],
    },
    {
        "gap_id": "graph_status_reconciliation_for_completed_missing_nodes",
        "priority": 3,
        "why": "Several graph nodes still show missing status even though later registry stages completed them. This can mislead future planning.",
        "next_step": "Patch graph status metadata for completed objectives without changing authority.",
        "blocked_authority": [],
    },
    {
        "gap_id": "tests_only_learning_signal_patch_plan",
        "priority": 4,
        "why": "Stage8854 pointed to a tests-only patch plan before implementation edits. That is still useful before touching trainer/data code.",
        "next_step": "Recover tests-only patch plan for learning-signal implementation.",
        "blocked_authority": ["training", "decoder_ce"],
    },
    {
        "gap_id": "eval_strict_unique_decoder_target_materialization",
        "priority": 5,
        "why": "Graph still records eval/strict unique target materialization as missing before any CE package can be meaningful.",
        "next_step": "Recover split-unique eval/strict target materialization or keep heldout non-CE evaluation as the boundary.",
        "blocked_authority": ["decoder_ce"],
    },
    {
        "gap_id": "verifier_guided_repair_target_materialization",
        "priority": 6,
        "why": "Denoise/repair controls exist, but verifier-guided repair target materialization is still listed as missing.",
        "next_step": "Recover verifier-guided repair target materialization controls; keep denoise CE closed.",
        "blocked_authority": ["denoise_ce", "runtime"],
    },
]


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    graph = load(GRAPH)
    registry = load(REGISTRY)
    rows = registry.get("rows", [])
    stage_names = {row.get("stage_name") for row in rows if row.get("passed") is True}
    missing_nodes = []
    stale_missing_nodes = []
    unresolved_missing_nodes = []
    for node in graph.get("nodes", []):
        status = node.get("status", "")
        if "missing" not in status and "blocked" not in status:
            continue
        item = {
            "id": node.get("id"),
            "name": node.get("name"),
            "kind": node.get("kind") or node.get("node_type"),
            "status": status,
        }
        missing_nodes.append(item)
        hint = RESOLUTION_HINTS.get(node.get("id"))
        if hint and hint in stage_names:
            item["resolved_by_stage"] = hint
            stale_missing_nodes.append(item)
        else:
            unresolved_missing_nodes.append(item)

    required_edges = [
        edge for edge in graph.get("edges", [])
        if (edge.get("edge_type") or edge.get("relation")) in {
            "required_before",
            "requires_contract_before_mining",
            "requires_source_gate",
            "requires_patch_readiness",
        }
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
            "missing_or_blocked_nodes": len(missing_nodes),
            "stale_missing_nodes": len(stale_missing_nodes),
            "unresolved_missing_nodes": len(unresolved_missing_nodes),
            "required_dependency_edges": len(required_edges),
            "true_gap_count": len(TRUE_GAPS),
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "commit_mining_authorized": False,
            "arxiv_repository_walk_authorized": False,
        },
        "artifacts": {
            "graph": str(GRAPH.relative_to(ROOT)),
            "registry": str(REGISTRY.relative_to(ROOT)),
            "gap_walk": str((OUT_DIR / "central_graph_gap_walk.json").relative_to(ROOT)),
        },
        "stale_missing_nodes": stale_missing_nodes,
        "unresolved_missing_nodes": unresolved_missing_nodes,
        "required_dependency_edges": required_edges,
        "true_gaps": TRUE_GAPS,
        "decision": "Central graph walk complete. Highest priority is dry-run commit inventory design; several graph statuses are stale and should be reconciled separately.",
        "next_best_step": "Recover dry-run commit inventory design without walking /arxiv repositories, or first reconcile stale graph statuses if planning confusion is the blocker.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "central_graph_gap_walk.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8863 Central Graph Gap Walk",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Graph nodes: `{card['metrics']['graph_nodes']}`",
        f"Graph edges: `{card['metrics']['graph_edges']}`",
        f"Missing/blocking nodes: `{card['metrics']['missing_or_blocked_nodes']}`",
        f"Stale missing nodes: `{card['metrics']['stale_missing_nodes']}`",
        f"Unresolved missing nodes: `{card['metrics']['unresolved_missing_nodes']}`",
        "",
        "## Priority Gaps",
        "",
        *[f"{gap['priority']}. `{gap['gap_id']}` - {gap['next_step']}" for gap in TRUE_GAPS],
        "",
        "Authority remains closed: no repository walking, mining, training, decoder CE, runtime, source/body emission, Gemma, scoring, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": True,
        "metrics": card["metrics"],
        "true_gaps": TRUE_GAPS,
        "next_best_step": card["next_best_step"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
