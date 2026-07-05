#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8846
NAME = "stage8846_registry_spine_reconciliation_after_learning_signal_contract"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_LEARNING_SIGNAL_CONTRACT_STAGE8846.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8843_registry_spine_reconciliation_after_authority_ticket_schema.json",
    ROOT / "runs/summaries/stage8844_learning_signal_contract.json",
    ROOT / "runs/summaries/stage8845_learning_signal_contract_graph_attachment.json",
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
            "learning_signal_rows": contract.get("rows"),
            "learning_signal_ready_rows": contract.get("learning_signal_contract_ready_rows"),
            "missing_telemetry_rows": contract.get("missing_telemetry_rows"),
            "missing_counterfactual_rows": contract.get("missing_counterfactual_rows"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled learning-signal contract into registry/spine; next missing target is dataset/trainer implementation plan.",
        "next_best_step": "Recover dataset/trainer implementation plan for learning-signal improvements. Keep training and decoder CE closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8846 Registry Spine Reconciliation After Learning Signal Contract", "", f"Passed: `{card['passed']}`", "", f"Learning-signal rows: `{card['metrics']['learning_signal_rows']}`", f"Ready rows: `{card['metrics']['learning_signal_ready_rows']}`", f"Missing telemetry rows: `{card['metrics']['missing_telemetry_rows']}`", f"Missing counterfactual rows: `{card['metrics']['missing_counterfactual_rows']}`", "", "Authority remains closed.", ""]), encoding="utf-8")
    marker = "## Stage8844-8846 Learning Signal Improvement Contract"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The learning-signal recovery is now represented as a contract rather than loose advice.",
            "",
            "- Stage8844 created contract rows for structured/policy targets: needs_verification, retrieval_coverage, ood_query, build_mode, patch_operator, edit_localization, symbol_binding, and verifier_repair.",
            "- The contract requires counterfactual siblings, row-field logits/losses, confusion matrices, margin/confidence/entropy, high-confidence wrong rows, token loss maps, per-row/per-module gradient norms, typed serialization, and explicit loss weighting.",
            "- Stage8845 attached the contract to the graph and linked it to `training_data.py`, `training_loop.py`, `training_telemetry_metrics.py`, and `modeling_transformer.py`.",
            "- Stage8846 reconciles registry/spine.",
            "",
            "Next boundary: recover the dataset/trainer implementation plan. It should list exact code changes and gates, but still must not authorize training or decoder CE.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
