#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8843
NAME = "stage8843_registry_spine_reconciliation_after_authority_ticket_schema"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_AUTHORITY_TICKET_SCHEMA_STAGE8843.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8839_registry_spine_reconciliation_after_runner_static_design.json",
    ROOT / "runs/summaries/stage8840_authority_ticket_schema.json",
    ROOT / "runs/summaries/stage8841_authority_ticket_schema_graph_attachment.json",
    ROOT / "runs/summaries/stage8842_authority_ticket_schema_gate_audit.json",
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
    names = {card_src.get("stage_name") for card_src in cards if card_src}
    names.add(NAME)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in names]
    for path, card_src in zip(SOURCES, cards):
        if card_src:
            rows.append({"stage": int(card_src["stage"]), "stage_name": card_src["stage_name"], "passed": card_src.get("passed") is True, "path": str(path), "authority": AUTHORITY_CLOSED, "next_best_step": card_src.get("next_best_step")})
    schema = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    graph = cards[2].get("metrics", {}) if len(cards) > 2 else {}
    gate = cards[3].get("metrics", {}) if len(cards) > 3 else {}
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
            "ticket_schema_rows": schema.get("rows"),
            "ticket_ready_rows": schema.get("authority_ticket_schema_ready_rows"),
            "ticket_gate_pass_rows": gate.get("ticket_gate_pass_rows"),
            "allowed_operation_rows": gate.get("allowed_operation_rows"),
            "opening_rows": gate.get("opening_rows"),
            "ready_for_model_execution": gate.get("ready_for_model_execution"),
            "ready_for_decoder_ce": gate.get("ready_for_decoder_ce"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled authority-ticket schema into registry/spine; next missing target is closed ticket-instance dry run.",
        "next_best_step": "Recover closed ticket-instance dry run. Do not run a model yet.",
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
        "# Stage8843 Registry Spine Reconciliation After Authority Ticket Schema",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Ticket schema rows: `{card['metrics']['ticket_schema_rows']}`",
        f"Ticket ready rows: `{card['metrics']['ticket_ready_rows']}`",
        f"Ticket gate pass rows: `{card['metrics']['ticket_gate_pass_rows']}`",
        f"Allowed-operation rows: `{card['metrics']['allowed_operation_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8840-8843 Authority Ticket Schema"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The future model-output capture path now has a closed-by-default authority-ticket schema.",
            "",
            "- Stage8840 created 240 ticket-schema rows with all gated operations denied by default: checkpoint load, forward, decode, model-output artifact write, decoder CE, denoise CE, runtime, Gemma, scoring, source/body emission, and promotion.",
            "- Stage8841 attached `schema:model_output_capture_authority_ticket_v1` to the graph.",
            "- Stage8842 audited all 240 rows: zero allowed-operation rows, zero opening rows, zero authority openings, and zero missing denials.",
            "- Stage8843 reconciles registry/spine.",
            "",
            "Next boundary: recover a closed ticket-instance dry run. That dry run should instantiate denied tickets and prove the runner would reject them before any future execution path is considered.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
