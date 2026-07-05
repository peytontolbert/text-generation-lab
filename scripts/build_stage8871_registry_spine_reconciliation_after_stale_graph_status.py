#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8871
NAME = "stage8871_registry_spine_reconciliation_after_stale_graph_status"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_STALE_GRAPH_STATUS_STAGE8871.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8869_stale_graph_status_reconciliation.json",
    ROOT / "runs/summaries/stage8870_reconciled_central_graph_gap_walk.json",
]
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


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    registry = load(REGISTRY) or {"rows": [], "metrics": {}}
    cards = [load(path) for path in SOURCES]
    failures = []
    for path, card_src in zip(SOURCES, cards):
        if not path.exists():
            failures.append(f"missing:{path}")
        elif card_src.get("passed") is not True:
            failures.append(f"failed:{card_src.get('stage_name')}")
    names = {NAME}
    names.update(card_src.get("stage_name") for card_src in cards if card_src)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in names]
    for path, card_src in zip(SOURCES, cards):
        if card_src:
            rows.append({
                "stage": int(card_src["stage"]),
                "stage_name": card_src["stage_name"],
                "passed": card_src.get("passed") is True,
                "path": str(path),
                "authority": AUTHORITY_CLOSED,
                "next_best_step": card_src.get("next_best_step"),
            })
    reconcile = cards[0].get("metrics", {}) if cards else {}
    gap = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "sources_indexed": len([c for c in cards if c]),
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
            "stale_nodes_patched": reconcile.get("stale_nodes_patched"),
            "resolved_reconciled_nodes": gap.get("resolved_reconciled_nodes"),
            "unresolved_missing_or_blocked_nodes": gap.get("unresolved_missing_or_blocked_nodes"),
            "prioritized_gap_count": gap.get("prioritized_gap_count"),
            "training_authorized": False,
            "decoder_ce_authorized": False,
            "commit_mining_authorized": False,
            "arxiv_repository_walk_authorized": False,
        },
        "decision": "Reconciled stale graph status cleanup and fresh graph gap walk into registry/spine.",
        "next_best_step": "If repository walking is explicitly requested, design future commit inventory preflight; otherwise recover verifier-guided repair target materialization controls.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True),
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8871 Registry Spine Reconciliation After Stale Graph Status",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Stale nodes patched: `{card['metrics']['stale_nodes_patched']}`",
        f"Resolved reconciled nodes: `{card['metrics']['resolved_reconciled_nodes']}`",
        f"Unresolved missing/blocking nodes: `{card['metrics']['unresolved_missing_or_blocked_nodes']}`",
        f"Prioritized gap count: `{card['metrics']['prioritized_gap_count']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8869-8871 Stale Graph Status Reconciliation"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stale graph statuses were reconciled so completed objectives no longer appear as missing.",
            "",
            "- Stage8869 patched 8 stale missing nodes to `resolved_by_reconciled_stage`.",
            "- Stage8870 reran the graph gap walk and preserved only true unresolved blockers.",
            "- Stage8871 reconciles registry/spine.",
            "",
            "Current priority: future commit inventory preflight only if repository walking is explicitly requested; otherwise verifier-guided repair target materialization controls.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
