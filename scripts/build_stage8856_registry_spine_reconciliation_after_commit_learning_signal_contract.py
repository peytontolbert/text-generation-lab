#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8857
NAME = "stage8857_registry_spine_reconciliation_after_commit_learning_signal_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_COMMIT_LEARNING_SIGNAL_CONTRACT_STAGE8857.md"
SOURCE = ROOT / "runs/summaries/stage8855_commit_learning_signal_contract.json"
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
    source = load(SOURCE)
    failures = []
    if not SOURCE.exists():
        failures.append(f"missing:{SOURCE}")
    elif source.get("passed") is not True:
        failures.append(f"failed:{source.get('stage_name')}")

    names = {NAME, "stage8856_registry_spine_reconciliation_after_commit_learning_signal_contract"}
    if source:
        names.add(source.get("stage_name"))
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in names]
    if source:
        rows.append({
            "stage": int(source["stage"]),
            "stage_name": source["stage_name"],
            "passed": source.get("passed") is True,
            "path": str(SOURCE),
            "authority": AUTHORITY_CLOSED,
            "next_best_step": source.get("next_best_step"),
        })
    m = source.get("metrics", {})
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
            "commit_contract_rows": m.get("rows"),
            "commit_contract_ready_rows": m.get("contract_ready_rows"),
            "commit_mining_authorized": m.get("commit_mining_authorized"),
            "arxiv_repository_walk_authorized": m.get("arxiv_repository_walk_authorized"),
            "training_authorized": m.get("training_authorized"),
            "decoder_ce_authorized": m.get("decoder_ce_authorized"),
        },
        "decision": "Reconciled commit-learning-signal contract into registry/spine. Commit mining remains closed until graph attachment and no-mining gate audit pass.",
        "next_best_step": "Attach commit-learning-signal contract to graph, then recover a no-mining gate audit. Keep training and decoder CE closed.",
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
        "# Stage8857 Registry Spine Reconciliation After Commit Learning Signal Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Commit contract rows: `{card['metrics']['commit_contract_rows']}`",
        f"Commit contract ready rows: `{card['metrics']['commit_contract_ready_rows']}`",
        f"Commit mining authorized: `{card['metrics']['commit_mining_authorized']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        f"Decoder CE authorized: `{card['metrics']['decoder_ce_authorized']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
