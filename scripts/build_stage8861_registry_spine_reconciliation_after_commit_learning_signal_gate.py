#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8861
NAME = "stage8861_registry_spine_reconciliation_after_commit_learning_signal_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_COMMIT_LEARNING_SIGNAL_GATE_STAGE8861.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8855_commit_learning_signal_contract.json",
    ROOT / "runs/summaries/stage8859_commit_learning_signal_graph_attachment.json",
    ROOT / "runs/summaries/stage8860_commit_learning_signal_no_mining_gate_audit.json",
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

    contract = cards[0].get("metrics", {}) if len(cards) > 0 else {}
    graph = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    audit = cards[2].get("metrics", {}) if len(cards) > 2 else {}
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
            "commit_contract_rows": contract.get("rows"),
            "commit_contract_ready_rows": contract.get("contract_ready_rows"),
            "gate_pass_rows": audit.get("gate_pass_rows"),
            "missing_contract_id_count": audit.get("missing_contract_id_count"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
            "commit_mining_authorized": audit.get("commit_mining_authorized"),
            "arxiv_repository_walk_authorized": audit.get("arxiv_repository_walk_authorized"),
            "training_authorized": audit.get("training_authorized"),
            "decoder_ce_authorized": audit.get("decoder_ce_authorized"),
        },
        "decision": "Reconciled commit-learning-signal graph attachment and no-mining gate into registry/spine.",
        "next_best_step": "Recover a dry-run commit inventory design without walking /arxiv repositories. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({
        "stage": STAGE,
        "stage_name": NAME,
        "passed": card["passed"],
        "path": str(SUMMARY),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card["next_best_step"],
    })
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
        "# Stage8861 Registry Spine Reconciliation After Commit Learning Signal Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Commit contract rows: `{card['metrics']['commit_contract_rows']}`",
        f"Gate pass rows: `{card['metrics']['gate_pass_rows']}`",
        f"Commit mining authorized: `{card['metrics']['commit_mining_authorized']}`",
        f"/arxiv repository walk authorized: `{card['metrics']['arxiv_repository_walk_authorized']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        f"Decoder CE authorized: `{card['metrics']['decoder_ce_authorized']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")

    marker = "## Stage8859-8861 Commit Learning Signal Graph And No-Mining Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The commit-learning-signal contract is now attached to the central graph and gated as no-mining.",
            "",
            "- Stage8859 attached `contract:commit_learning_signal_v1` to the graph and linked it to source lineage, provenance, contamination, locked-eval, cluster/near-duplicate, and junk/OOD gates.",
            "- Stage8860 audited all 10 contract rows: route is `CONTRACT_ONLY_NO_MINING`, anti-cheat openings are false, source gate requirements are present, large-commit decoder targets remain blocked, and all authority/loss masks are closed.",
            "- Stage8861 reconciles registry/spine.",
            "",
            "Next boundary: recover a dry-run commit inventory design. It may define how to inspect repository metadata later, but it still must not walk `/arxiv/repositories`, read commits, emit training rows, train, or open decoder CE.",
            "",
        ]), encoding="utf-8")

    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
