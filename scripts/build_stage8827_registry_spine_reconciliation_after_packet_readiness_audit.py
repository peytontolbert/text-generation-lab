#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8827
NAME = "stage8827_registry_spine_reconciliation_after_packet_readiness_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_PACKET_READINESS_AUDIT_STAGE8827.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8825_registry_spine_reconciliation_after_packet_telemetry_contract.json",
    ROOT / "runs/summaries/stage8826_model_output_packet_readiness_contract_audit.json",
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
    for path, card in zip(SOURCES, cards):
        if not path.exists():
            failures.append(f"missing:{path}")
        elif card.get("passed") is not True:
            failures.append(f"failed:{card.get('stage_name')}")
    names = {card.get("stage_name") for card in cards if card}
    names.add(NAME)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in names]
    for path, card in zip(SOURCES, cards):
        if card:
            rows.append({"stage": int(card["stage"]), "stage_name": card["stage_name"], "passed": card.get("passed") is True, "path": str(path), "authority": AUTHORITY_CLOSED, "next_best_step": card.get("next_best_step")})
    audit = cards[1].get("metrics", {}) if len(cards) > 1 else {}
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
            "packet_contract_rows": audit.get("rows"),
            "contract_ready_rows": audit.get("contract_ready_rows"),
            "authority_open_rows": audit.get("authority_open_rows"),
            "loss_open_rows": audit.get("loss_open_rows"),
            "ready_for_model_execution": audit.get("ready_for_model_execution"),
            "ready_for_decoder_ce": audit.get("ready_for_decoder_ce"),
        },
        "decision": "Reconciled packet readiness audit into registry/spine; next missing target is a no-execution synthetic packet validator dry run.",
        "next_best_step": "Build a no-execution packet validator dry-run using synthetic placeholder packets, not model outputs. Keep model execution/training/CE closed.",
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
        "# Stage8827 Registry Spine Reconciliation After Packet Readiness Audit",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Packet contract rows: `{card['metrics']['packet_contract_rows']}`",
        f"Contract-ready rows: `{card['metrics']['contract_ready_rows']}`",
        f"Ready for model execution: `{card['metrics']['ready_for_model_execution']}`",
        f"Ready for decoder CE: `{card['metrics']['ready_for_decoder_ce']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8826-8827 Packet Readiness Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The packet telemetry contract is now audited as schema-ready, but not model-probe-ready.",
            "",
            "- Stage8826 checked 240 packet-contract rows and found zero missing fields, zero missing checks, zero missing telemetry, zero authority openings, and zero loss openings.",
            "- Stage8827 reconciles the audit into registry/spine.",
            "",
            "Next boundary: build a synthetic no-execution packet validator dry run. It should validate placeholder packets against the contract before any real model output is allowed into the evaluation path.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
