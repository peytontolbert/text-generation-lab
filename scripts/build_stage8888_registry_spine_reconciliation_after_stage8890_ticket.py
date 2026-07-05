#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8888
NAME = "stage8888_registry_spine_reconciliation_after_stage8890_ticket"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_STAGE8890_TICKET_STAGE8888.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8886_stage8890_inactive_execution_ticket_design.json",
    ROOT / "runs/summaries/stage8887_stage8890_inactive_execution_ticket_gate_audit.json",
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
        elif any((card_src.get("authority") or {}).values()):
            failures.append(f"authority_open:{card_src.get('stage_name')}")
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
    gate_metrics = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "sources_indexed": len([card_src for card_src in cards if card_src]),
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
            "stage8890_ticket_gate_passed": gate_metrics.get("gate_failures") == 0,
            "stage8890_ticket_status": gate_metrics.get("ticket_status"),
            "stage8890_command_materialized": gate_metrics.get("command_materialized"),
            "training_authorized": False,
            "model_execution_authorized_now": False,
            "decoder_ce_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_authorized_flag": False,
        },
        "decision": "Indexed inactive Stage8890 ticket design and gate audit. Stage8890 remains unrun and no authority is opened.",
        "next_best_step": "Wait for an explicit user decision before issuing any live Stage8890 one-run authorization. Safe alternatives: deepen dataset/module recovery or design more no-execution gates.",
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
    registry["passed"] = card["passed"]
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
        "# Stage8888 Registry Spine Reconciliation After Stage8890 Ticket",
        "",
        f"Passed: `{card['passed']}`",
        "",
        "Indexed:",
        "",
        "- Stage8886 inactive Stage8890 ticket design",
        "- Stage8887 inactive Stage8890 ticket gate audit",
        "",
        "Stage8890 remains unrun. The ticket is a closed, inactive design artifact, not execution authority.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8886-8888 Inactive Stage8890 Ticket"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Stage8886 created a draft inactive authority ticket for the future Stage8890 tiny structured-policy probe. Stage8887 audited it and required it to remain commandless, non-executing, structured-aux only, and guarded by the Stage8862 interpretability artifact contract. Stage8888 reconciles the ticket into the registry/spine.",
            "",
            "This does not authorize model execution, training, decoder CE, denoise CE, runtime, source/body emission, Gemma, harness, scoring, checkpoint export, controller merge, or promotion. Stage8890 is reserved for a future explicit one-run authorization decision.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
