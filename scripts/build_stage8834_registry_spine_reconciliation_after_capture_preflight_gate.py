#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8834
NAME = "stage8834_registry_spine_reconciliation_after_capture_preflight_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_CAPTURE_PREFLIGHT_GATE_STAGE8834.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8830_registry_spine_reconciliation_after_synthetic_packet_validator.json",
    ROOT / "runs/summaries/stage8831_model_output_capture_preflight_design.json",
    ROOT / "runs/summaries/stage8832_model_output_capture_preflight_graph_attachment.json",
    ROOT / "runs/summaries/stage8833_static_capture_preflight_gate_audit.json",
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
    preflight = cards[1].get("metrics", {}) if len(cards) > 1 else {}
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
            "preflight_rows": preflight.get("rows"),
            "static_gate_pass_rows": gate.get("static_gate_pass_rows"),
            "model_output_rows": gate.get("model_output_rows"),
            "model_execution_ready_rows": gate.get("model_execution_ready_rows"),
            "decoder_ce_ready_rows": gate.get("decoder_ce_ready_rows"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled capture preflight design and static gate into registry/spine; next missing target is an authority-ticket schema for future capture.",
        "next_best_step": "Recover authority-ticket schema for future model-output capture. Do not run a model yet.",
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
        "# Stage8834 Registry Spine Reconciliation After Capture Preflight Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Preflight rows: `{card['metrics']['preflight_rows']}`",
        f"Static gate pass rows: `{card['metrics']['static_gate_pass_rows']}`",
        f"Model output rows: `{card['metrics']['model_output_rows']}`",
        f"Model execution ready rows: `{card['metrics']['model_execution_ready_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8831-8834 Authority-Closed Model Output Capture Preflight"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The future model-output capture path now has a preflight design and a static closed gate, but still no model execution.",
            "",
            "- Stage8831 built 240 capture-preflight design rows from synthetic placeholder packets.",
            "- Stage8832 attached `design:authority_closed_model_output_capture_preflight_v1` to the graph and introduced `objective:static_capture_preflight_gate_audit`.",
            "- Stage8833 validated all 240 rows through the static gate with zero model-output, probe-ready, model-execution, decoder-CE, authority, or loss openings.",
            "- Stage8834 reconciles registry/spine.",
            "",
            "Next boundary: recover an authority-ticket schema for future model-output capture. It must describe the exact authorization fields needed before checkpoint loading or model forward/decode can ever be considered.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
