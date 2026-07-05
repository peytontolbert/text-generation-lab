#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8850
NAME = "stage8850_registry_spine_reconciliation_after_learning_signal_implementation_plan"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_LEARNING_SIGNAL_IMPLEMENTATION_PLAN_STAGE8850.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8846_registry_spine_reconciliation_after_learning_signal_contract.json",
    ROOT / "runs/summaries/stage8847_learning_signal_implementation_plan.json",
    ROOT / "runs/summaries/stage8848_learning_signal_implementation_plan_graph_attachment.json",
    ROOT / "runs/summaries/stage8849_learning_signal_implementation_plan_gate_audit.json",
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
    plan = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    graph = cards[2].get("metrics", {}) if len(cards) > 2 else {}
    audit = cards[3].get("metrics", {}) if len(cards) > 3 else {}
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
            "plan_rows": plan.get("rows"),
            "plan_ready_rows": plan.get("implementation_plan_ready_rows"),
            "plan_gate_pass_rows": audit.get("plan_gate_pass_rows"),
            "missing_plan_id_count": audit.get("missing_plan_id_count"),
            "missing_file_count": audit.get("missing_file_count"),
            "training_authorized": audit.get("training_authorized"),
            "decoder_ce_authorized": audit.get("decoder_ce_authorized"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled learning-signal implementation plan into registry/spine; next missing target is code-patch readiness checklist.",
        "next_best_step": "Recover code-patch readiness checklist for learning-signal implementation. Keep training and decoder CE closed.",
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
        "# Stage8850 Registry Spine Reconciliation After Learning Signal Implementation Plan",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Plan rows: `{card['metrics']['plan_rows']}`",
        f"Plan ready rows: `{card['metrics']['plan_ready_rows']}`",
        f"Plan gate pass rows: `{card['metrics']['plan_gate_pass_rows']}`",
        f"Training authorized: `{card['metrics']['training_authorized']}`",
        f"Decoder CE authorized: `{card['metrics']['decoder_ce_authorized']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8847-8850 Learning Signal Dataset/Trainer Implementation Plan"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The learning-signal contract now has a file-specific dataset/trainer implementation plan.",
            "",
            "- Stage8847 created six implementation-plan rows: typed input serialization, counterfactual sibling manifest gate, structured-head telemetry, gradient/loss-weight telemetry, telemetry helper expansion, and structured-head target mapping.",
            "- Stage8848 attached the plan to the graph and linked it to `training_data.py`, `training_loop.py`, `training_telemetry_metrics.py`, and `modeling_transformer.py`.",
            "- Stage8849 audited the plan: all required plan IDs and files are present, all rows have planned changes and acceptance checks, and training/decoder CE remain closed.",
            "- Stage8850 reconciles registry/spine.",
            "",
            "Next boundary: recover a code-patch readiness checklist. It should define the exact preconditions before modifying training/data code, but still must not authorize training or decoder CE.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
