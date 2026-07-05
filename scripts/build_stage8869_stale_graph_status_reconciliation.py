#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8869
NAME = "stage8869_stale_graph_status_reconciliation"
BASE = ROOT / "runs/local/artifacts/stage8867_commit_inventory_dry_run_graph_attachment/central_research_graph_with_commit_inventory_dry_run.json"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
GAP_WALK = ROOT / "runs/local/artifacts/stage8863_central_graph_gap_walk/central_graph_gap_walk.json"
OUT_DIR = ROOT / "runs/local/artifacts" / NAME
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "STALE_GRAPH_STATUS_RECONCILIATION_STAGE8869.md"
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
    graph = load(BASE)
    registry = load(REGISTRY)
    gap_walk = load(GAP_WALK)
    passed_stage_names = {row.get("stage_name") for row in registry.get("rows", []) if row.get("passed") is True}
    stale = gap_walk.get("stale_missing_nodes", [])
    patched_nodes = []
    skipped_nodes = []
    by_id = {node.get("id"): node for node in graph.get("nodes", []) if node.get("id")}
    for item in stale:
        node_id = item.get("id")
        resolved_by = item.get("resolved_by_stage")
        node = by_id.get(node_id)
        if not node or resolved_by not in passed_stage_names:
            skipped_nodes.append(item)
            continue
        old_status = node.get("status")
        node["status"] = "resolved_by_reconciled_stage"
        node["resolved_by_stage"] = resolved_by
        node["previous_status"] = old_status
        node["reconciled_by_stage"] = NAME
        node["authority"] = AUTHORITY_CLOSED
        patched_nodes.append({
            "id": node_id,
            "old_status": old_status,
            "new_status": node["status"],
            "resolved_by_stage": resolved_by,
        })

    out = {"version": NAME, "nodes": graph.get("nodes", []), "edges": graph.get("edges", [])}
    graph_path = OUT_DIR / "central_research_graph_with_stale_status_reconciliation.json"
    nodes_path = OUT_DIR / "central_research_graph_with_stale_status_reconciliation_nodes.jsonl"
    edges_path = OUT_DIR / "central_research_graph_with_stale_status_reconciliation_edges.jsonl"
    graph_path.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    nodes_path.write_text("".join(json.dumps(node, sort_keys=True) + "\n" for node in out["nodes"]), encoding="utf-8")
    edges_path.write_text("".join(json.dumps(edge, sort_keys=True) + "\n" for edge in out["edges"]), encoding="utf-8")
    passed = len(patched_nodes) == len(stale) and not skipped_nodes
    metrics = {
        **AUTHORITY_CLOSED,
        "authority_rows": 0,
        "graph_nodes": len(out["nodes"]),
        "graph_edges": len(out["edges"]),
        "stale_nodes_seen": len(stale),
        "stale_nodes_patched": len(patched_nodes),
        "stale_nodes_skipped": len(skipped_nodes),
        "unresolved_missing_nodes_preserved": len(gap_walk.get("unresolved_missing_nodes", [])),
        "arxiv_repository_walk_authorized": False,
        "commit_mining_authorized": False,
        "training_authorized": False,
        "decoder_ce_authorized": False,
    }
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": passed,
        "authority": AUTHORITY_CLOSED,
        "metrics": metrics,
        "artifacts": {
            "graph": str(graph_path.relative_to(ROOT)),
            "nodes_jsonl": str(nodes_path.relative_to(ROOT)),
            "edges_jsonl": str(edges_path.relative_to(ROOT)),
            "gap_walk": str(GAP_WALK.relative_to(ROOT)),
        },
        "patched_nodes": patched_nodes,
        "skipped_nodes": skipped_nodes,
        "decision": "Reconciled stale graph statuses for completed objectives. Unresolved blockers were preserved unchanged.",
        "next_best_step": "Run a fresh central graph gap walk against the reconciled graph to confirm only true unresolved blockers remain.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (OUT_DIR / "stale_graph_status_reconciliation_card.json").write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8869 Stale Graph Status Reconciliation",
        "",
        f"Passed: `{passed}`",
        "",
        f"Stale nodes seen: `{metrics['stale_nodes_seen']}`",
        f"Stale nodes patched: `{metrics['stale_nodes_patched']}`",
        f"Stale nodes skipped: `{metrics['stale_nodes_skipped']}`",
        f"Unresolved missing nodes preserved: `{metrics['unresolved_missing_nodes_preserved']}`",
        "",
        "Patched nodes:",
        "",
        *[f"- `{node['id']}` -> `{node['resolved_by_stage']}`" for node in patched_nodes],
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if passed else 1)


if __name__ == "__main__":
    main()
