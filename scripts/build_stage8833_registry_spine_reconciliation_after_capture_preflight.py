#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8833
NAME = "stage8833_registry_spine_reconciliation_after_capture_preflight"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_CAPTURE_PREFLIGHT_STAGE8833.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8830_registry_spine_reconciliation_after_synthetic_packet_validator.json",
    ROOT / "runs/summaries/stage8831_model_output_capture_preflight_design.json",
    ROOT / "runs/summaries/stage8832_model_output_capture_preflight_graph_attachment.json",
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
    for path, card_src in zip(SOURCES, cards):
        if card_src:
            rows.append({"stage": int(card_src["stage"]), "stage_name": card_src["stage_name"], "passed": card_src.get("passed") is True, "path": str(path), "authority": AUTHORITY_CLOSED, "next_best_step": card_src.get("next_best_step")})
    preflight = cards[1].get("metrics", {}) if len(cards) > 1 else {}
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
            "preflight_design_ready_rows": preflight.get("preflight_design_ready_rows"),
            "model_output_rows": preflight.get("model_output_rows"),
            "artifact_write_rows": preflight.get("artifact_write_rows"),
            "ready_for_model_execution": preflight.get("ready_for_model_execution"),
            "ready_for_decoder_ce": preflight.get("ready_for_decoder_ce"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled authority-closed model-output capture preflight into registry/spine; next missing target is a preflight audit.",
        "next_best_step": "Audit model-output capture preflight design. Do not run a model yet.",
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
    DOC.write_text("\n".join(["# Stage8833 Registry Spine Reconciliation After Capture Preflight", "", f"Passed: `{card['passed']}`", "", f"Preflight-design-ready rows: `{card['metrics']['preflight_design_ready_rows']}`", f"Model output rows: `{card['metrics']['model_output_rows']}`", f"Artifact write rows: `{card['metrics']['artifact_write_rows']}`", f"Ready for model execution: `{card['metrics']['ready_for_model_execution']}`", "", "Authority remains closed.", ""]), encoding="utf-8")
    marker = "## Stage8831-8833 Authority-Closed Model Output Capture Preflight"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The next decoder-eval boundary is now a design-only capture preflight, not a model run.",
            "",
            "- Stage8831 built 240 authority-closed capture-preflight rows from synthetic placeholder packets: zero model outputs, zero artifact writes, zero loss openings, and zero execution authority.",
            "- Stage8832 attached the capture preflight to the graph and introduced `objective:model_output_capture_preflight_audit`.",
            "- Stage8833 reconciles registry/spine.",
            "",
            "Next boundary: audit the capture preflight design. Only after that should a future runner design be considered, and even then it must remain behind explicit model-execution and CE authority gates.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
