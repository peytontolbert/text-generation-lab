#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8795
NAME = "stage8795_registry_spine_reconciliation"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_STAGE8795.md"
SOURCES = [
    ROOT / "runs/summaries/stage8791_query_expansion_rewriter_readiness.json",
    ROOT / "runs/summaries/stage8792_parallel_recovery_readiness_audit.json",
    ROOT / "runs/summaries/stage8793_query_recovery_graph_attachment.json",
    ROOT / "runs/summaries/stage8794_support_stack_integration_audit_no_registry.json",
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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"passed": True, "rows": [], "metrics": {}}
    source_cards = [load_json(path) for path in SOURCES]
    failures = []
    for path, card in zip(SOURCES, source_cards):
        if not path.exists():
            failures.append(f"missing_source:{path}")
        elif card.get("passed") is not True:
            failures.append(f"source_failed:{card.get('stage_name', path.name)}")
    source_stage_names = {card.get("stage_name") for card in source_cards if card}
    source_stage_names.add(NAME)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in source_stage_names]
    for path, card in zip(SOURCES, source_cards):
        if not card:
            continue
        rows.append({
            "stage": int(card["stage"]),
            "stage_name": card["stage_name"],
            "passed": bool(card.get("passed") is True),
            "path": str(path),
            "authority": AUTHORITY_CLOSED,
            "next_best_step": card.get("next_best_step"),
        })
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "sources_indexed": len([card for card in source_cards if card]),
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
        },
        "decision": (
            "Reconciled reconstructed registry with Stage8791-8794 recovery frontier and recorded spine update boundary."
            if not failures
            else "Registry/spine reconciliation failed; source summaries must be fixed first."
        ),
        "next_best_step": "Proceed to bounded decoder argument candidate controls only after confirming registry/spine reconciliation and support-stack audit remain clean.",
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
    rows = sorted(rows, key=lambda row: int(row.get("stage", -1)))
    registry["rows"] = rows
    historical_failed_rows = sum(1 for row in rows if row.get("passed") is not True)
    registry["passed"] = not failures
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "historical_failed_rows": historical_failed_rows,
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8795 Registry Spine Reconciliation",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Indexed Stage8791-8794 into the reconstructed registry and recorded the current no-authority frontier.",
        "",
        f"Registry rows before: `{card['metrics']['registry_rows_before']}`",
        f"Registry rows after: `{card['metrics']['registry_rows_after']}`",
        "",
        "Authority remains closed: no mining, training, runtime, decoder CE, denoise CE, scoring, source/body emission, Gemma, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
