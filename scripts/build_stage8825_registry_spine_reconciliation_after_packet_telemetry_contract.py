#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8825
NAME = "stage8825_registry_spine_reconciliation_after_packet_telemetry_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_PACKET_TELEMETRY_CONTRACT_STAGE8825.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8822_registry_spine_reconciliation_after_heldout_non_ce_eval_design.json",
    ROOT / "runs/summaries/stage8823_model_output_packet_telemetry_contract_manifest.json",
    ROOT / "runs/summaries/stage8824_model_output_packet_telemetry_graph_attachment.json",
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
    contract = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    graph = cards[2].get("metrics", {}) if len(cards) > 2 else {}
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
            "packet_contract_rows": contract.get("rows"),
            "packet_probe_ready_rows": contract.get("probe_ready_rows"),
            "decoder_ce_eligible_now_rows": contract.get("decoder_ce_eligible_now_rows"),
            "loss_rows": contract.get("loss_rows"),
            "missing_required_field_rows": contract.get("missing_required_field_rows"),
            "missing_required_check_rows": contract.get("missing_required_check_rows"),
            "missing_required_telemetry_rows": contract.get("missing_required_telemetry_rows"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled model-output packet telemetry contract into registry/spine; next missing target is a no-execution future probe packet readiness audit.",
        "next_best_step": "Build no-execution future probe packet readiness audit. Keep execution/training/CE closed.",
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
        "# Stage8825 Registry Spine Reconciliation After Packet Telemetry Contract",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Packet contract rows: `{card['metrics']['packet_contract_rows']}`",
        f"Probe-ready rows: `{card['metrics']['packet_probe_ready_rows']}`",
        f"Decoder CE eligible now rows: `{card['metrics']['decoder_ce_eligible_now_rows']}`",
        f"Loss rows: `{card['metrics']['loss_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8823-8825 Model Output Packet Telemetry Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The heldout non-CE decoder path now has an explicit future output-packet contract instead of ad hoc probe logs.",
            "",
            "- Stage8823 built 240 eval/strict packet-contract rows requiring schema checks, leak checks, surface checks, budget checks, grounded-argument checks, locked-eval checks, cluster duplicate checks, and tensor/logit decode telemetry.",
            "- Stage8824 attached `contract:model_output_packet_telemetry_v1` to the central graph and introduced `objective:future_probe_packet_readiness_audit`.",
            "- Stage8825 reconciles registry/spine.",
            "",
            "Next boundary: build a no-execution future probe packet readiness audit. It should validate packet fields/checks/telemetry and authority bits before any model probe is considered. Decoder CE, denoise CE, runtime, Gemma, scoring, source/body emission, and promotion remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
