#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8868
NAME = "stage8868_registry_spine_reconciliation_after_commit_inventory_dry_run"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_COMMIT_INVENTORY_DRY_RUN_STAGE8868.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8863_central_graph_gap_walk.json",
    ROOT / "runs/summaries/stage8865_commit_inventory_dry_run_design.json",
    ROOT / "runs/summaries/stage8866_commit_inventory_dry_run_gate_audit.json",
    ROOT / "runs/summaries/stage8867_commit_inventory_dry_run_graph_attachment.json",
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

    names = {NAME, "stage8864_commit_inventory_dry_run_design", "stage8865_commit_inventory_dry_run_gate_audit", "stage8866_commit_inventory_dry_run_graph_attachment"}
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
    design = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    audit = cards[2].get("metrics", {}) if len(cards) > 2 else {}
    graph = cards[3].get("metrics", {}) if len(cards) > 3 else {}
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
            "dry_run_design_rows": design.get("rows"),
            "dry_run_ready_rows": design.get("dry_run_design_ready_rows"),
            "gate_pass_rows": audit.get("gate_pass_rows"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
            "arxiv_repository_walk_authorized": audit.get("arxiv_repository_walk_authorized"),
            "commit_reads_authorized": audit.get("commit_reads_authorized"),
            "commit_mining_authorized": audit.get("commit_mining_authorized"),
            "training_authorized": audit.get("training_authorized"),
            "decoder_ce_authorized": audit.get("decoder_ce_authorized"),
        },
        "decision": "Reconciled dry-run commit inventory design, gate audit, and graph attachment. Repository walking remains closed.",
        "next_best_step": "Recover stale graph status reconciliation, or design a future commit inventory preflight if repository walking is explicitly requested later.",
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
        "# Stage8868 Registry Spine Reconciliation After Commit Inventory Dry Run",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Dry-run design rows: `{card['metrics']['dry_run_design_rows']}`",
        f"Gate pass rows: `{card['metrics']['gate_pass_rows']}`",
        f"/arxiv repository walk authorized: `{card['metrics']['arxiv_repository_walk_authorized']}`",
        f"Commit reads authorized: `{card['metrics']['commit_reads_authorized']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        f"Decoder CE authorized: `{card['metrics']['decoder_ce_authorized']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8865-8868 Commit Inventory Dry-Run Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The commit inventory gap is filled as a dry-run design only.",
            "",
            "- Stage8865 defines inventory fields, commit metadata fields, caps, and source gates.",
            "- Stage8866 audits that the design is zero-walk, zero-commit-read, zero-diff-body, zero-patch-body, and zero-training-row.",
            "- Stage8867 attaches the design to the graph and creates `objective:future_commit_inventory_preflight` as the next missing target.",
            "- Stage8868 reconciles registry/spine.",
            "",
            "Repository walking, commit reads, mining, training, decoder CE, runtime, source/body emission, Gemma, scoring, and promotion remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
