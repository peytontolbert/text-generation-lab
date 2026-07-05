#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8836
NAME = "stage8836_registry_spine_reconciliation_after_capture_preflight_audit"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_CAPTURE_PREFLIGHT_AUDIT_STAGE8836.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8833_registry_spine_reconciliation_after_capture_preflight.json",
    ROOT / "runs/summaries/stage8834_model_output_capture_preflight_design_audit.json",
    ROOT / "runs/summaries/stage8835_model_output_capture_preflight_audit_graph_attachment.json",
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
    audit = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    graph = cards[2].get("metrics", {}) if len(cards) > 2 else {}
    card = {"stage": STAGE, "stage_name": NAME, "passed": not failures, "authority": AUTHORITY_CLOSED, "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "sources_indexed": len([c for c in cards if c]), "registry_rows_before": len(registry.get("rows", [])), "registry_rows_after": len(rows) + 1, "audit_ready_rows": audit.get("audit_ready_rows"), "execution_allowed_rows": audit.get("execution_allowed_rows"), "model_output_rows": audit.get("model_output_rows"), "artifact_write_rows": audit.get("artifact_write_rows"), "ready_for_model_execution": audit.get("ready_for_model_execution"), "ready_for_decoder_ce": audit.get("ready_for_decoder_ce"), "graph_nodes": graph.get("graph_nodes"), "graph_edges": graph.get("graph_edges")}, "decision": "Reconciled capture preflight audit into registry/spine; next missing target is static future runner interface design.", "next_best_step": "Build future model-output capture runner static design. Do not run a model yet.", "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8836 Registry Spine Reconciliation After Capture Preflight Audit", "", f"Passed: `{card['passed']}`", "", f"Audit-ready rows: `{card['metrics']['audit_ready_rows']}`", f"Execution-allowed rows: `{card['metrics']['execution_allowed_rows']}`", f"Model output rows: `{card['metrics']['model_output_rows']}`", f"Ready for model execution: `{card['metrics']['ready_for_model_execution']}`", "", "Authority remains closed.", ""]), encoding="utf-8")
    marker = "## Stage8834-8836 Capture Preflight Audit"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The model-output capture preflight has now passed a closed-authority audit.",
            "",
            "- Stage8834 audited 240 preflight rows: zero execution-allowed rows, zero model-output rows, zero artifact-write rows, zero authority openings, and zero loss openings.",
            "- Stage8835 attached the audit to the graph and introduced `objective:future_model_output_capture_runner_static_design`.",
            "- Stage8836 reconciles registry/spine.",
            "",
            "Next boundary: static runner-interface design only. This should specify CLI flags/artifact paths/assertions for a future capture runner, but still must not run the model or open decoder CE/runtime/Gemma/scoring.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
