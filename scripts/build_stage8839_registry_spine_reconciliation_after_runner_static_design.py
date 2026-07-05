#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8839
NAME = "stage8839_registry_spine_reconciliation_after_runner_static_design"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_RUNNER_STATIC_DESIGN_STAGE8839.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8836_registry_spine_reconciliation_after_capture_preflight_audit.json",
    ROOT / "runs/summaries/stage8837_model_output_capture_runner_static_design.json",
    ROOT / "runs/summaries/stage8838_runner_static_design_graph_attachment.json",
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
    runner = cards[1].get("metrics", {}) if len(cards) > 1 else {}
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
            "runner_static_rows": runner.get("rows"),
            "runner_static_design_ready_rows": runner.get("runner_static_design_ready_rows"),
            "execution_open_rows": runner.get("execution_open_rows"),
            "model_output_rows": runner.get("model_output_rows"),
            "ready_for_model_execution": runner.get("ready_for_model_execution"),
            "ready_for_decoder_ce": runner.get("ready_for_decoder_ce"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled future runner static design into registry/spine; next missing target is authority-ticket schema.",
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
        "# Stage8839 Registry Spine Reconciliation After Runner Static Design",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Runner static rows: `{card['metrics']['runner_static_rows']}`",
        f"Runner static design ready rows: `{card['metrics']['runner_static_design_ready_rows']}`",
        f"Execution-open rows: `{card['metrics']['execution_open_rows']}`",
        f"Model output rows: `{card['metrics']['model_output_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8837-8839 Future Runner Static Design"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The future model-output capture runner now has a static interface design, but still no runnable model path.",
            "",
            "- Stage8837 defined required CLI flags, artifact paths, and assertions for a future runner. All 240 rows keep checkpoint loading, model forward, decode, CE, runtime, Gemma, scoring, and artifact writes closed.",
            "- Stage8838 attached `design:future_model_output_capture_runner_static_v1` to the graph and introduced `objective:future_model_output_capture_authority_ticket_schema`.",
            "- Stage8839 reconciles registry/spine and restores latest-stage metrics after the concurrent Stage8834-8836 path.",
            "",
            "Next boundary: recover the authority-ticket schema. This ticket must define the exact explicit authorization fields required before any future checkpoint load, forward pass, decode, output artifact write, CE, runtime, Gemma, or scoring path can open.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
