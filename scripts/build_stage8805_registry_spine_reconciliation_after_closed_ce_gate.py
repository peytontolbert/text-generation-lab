#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8805
NAME = "stage8805_registry_spine_reconciliation_after_closed_ce_gate"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_CLOSED_CE_GATE_STAGE8805.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8801_parallel_bounded_decoder_audit_reconciliation.json",
    ROOT / "runs/summaries/stage8802_closed_bounded_decoder_ce_package_gate.json",
    ROOT / "runs/summaries/stage8803_closed_bounded_decoder_ce_package_gate_audit.json",
    ROOT / "runs/summaries/stage8804_closed_bounded_decoder_ce_gate_graph_attachment.json",
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
    cards = [load(p) for p in SOURCES]
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
            rows.append({
                "stage": int(card["stage"]),
                "stage_name": card["stage_name"],
                "passed": card.get("passed") is True,
                "path": str(path),
                "authority": AUTHORITY_CLOSED,
                "next_best_step": card.get("next_best_step"),
            })
    ce_gate = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    graph = cards[3].get("metrics", {}) if len(cards) > 3 else {}
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
            "closed_ce_gate_rows": ce_gate.get("rows"),
            "closed_ce_candidate_needs_target_text_rows": (ce_gate.get("gate_decision_counts") or {}).get("CE_CANDIDATE_NEEDS_SOURCE_BACKED_TARGET_TEXT"),
            "closed_ce_eligible_now_rows": ce_gate.get("decoder_ce_eligible_now_rows"),
            "closed_ce_loss_mask_rows": ce_gate.get("loss_mask_rows"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled registry/spine after closed bounded decoder CE gate; next missing module is source-backed decoder target materialization controls." if not failures else "Registry/spine reconciliation failed.",
        "next_best_step": "Recover source-backed decoder target materialization controls. Keep decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion closed.",
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
        "# Stage8805 Registry Spine Reconciliation After Closed CE Gate",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Closed CE gate rows: `{card['metrics']['closed_ce_gate_rows']}`",
        f"Candidate rows needing target text: `{card['metrics']['closed_ce_candidate_needs_target_text_rows']}`",
        f"CE eligible now rows: `{card['metrics']['closed_ce_eligible_now_rows']}`",
        f"Loss-mask rows: `{card['metrics']['closed_ce_loss_mask_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8802-8805 Closed Bounded Decoder CE Gate"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "The recovered bounded decoder CE path is now represented as a closed gate, not as training authority.",
            "",
            "- Stage8802 built 504 closed CE package-gate rows from the audited argument controls.",
            "- Stage8803 audited that zero rows have decoder CE loss enabled, zero rows are CE-eligible now, all gate-status fields are complete, and all authority remains closed.",
            "- Stage8804 attached the gate to the central graph and introduced `objective:source_backed_decoder_target_materialization` as the next missing recovery target.",
            "- Stage8805 updates the registry/spine frontier accordingly.",
            "",
            "Current hard boundary: 360 rows are future CE candidates only after source-backed target text materialization. 72 are blocked for long-output/budget and 72 are blocked for retrieve-more. No decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, or promotion is authorized.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
