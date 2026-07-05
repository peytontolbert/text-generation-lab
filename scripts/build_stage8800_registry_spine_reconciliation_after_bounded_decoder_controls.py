#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8800
NAME = "stage8800_registry_spine_reconciliation_after_bounded_decoder_controls"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_BOUNDED_DECODER_CONTROLS_STAGE8800.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8791_query_expansion_rewriter_readiness.json",
    ROOT / "runs/summaries/stage8792_parallel_recovery_readiness_audit.json",
    ROOT / "runs/summaries/stage8793_query_recovery_graph_attachment.json",
    ROOT / "runs/summaries/stage8794_support_stack_integration_audit_no_registry.json",
    ROOT / "runs/summaries/stage8795_registry_spine_reconciliation.json",
    ROOT / "runs/summaries/stage8796_current_gap_audit_after_registry_reconciliation.json",
    ROOT / "runs/summaries/stage8797_bounded_decoder_argument_controls_manifest.json",
    ROOT / "runs/summaries/stage8798_bounded_decoder_argument_controls_shortcut_gate.json",
    ROOT / "runs/summaries/stage8799_bounded_decoder_argument_controls_graph_attachment.json",
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


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def row_for(path: Path, card: dict) -> dict:
    return {
        "stage": int(card["stage"]),
        "stage_name": card["stage_name"],
        "passed": bool(card.get("passed") is True),
        "path": str(path),
        "authority": AUTHORITY_CLOSED,
        "next_best_step": card.get("next_best_step"),
    }


def main() -> None:
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    registry = load_json(REGISTRY) or {"passed": True, "rows": [], "metrics": {}}
    source_cards = [load_json(path) for path in SOURCES]
    failures = []
    for path, card in zip(SOURCES, source_cards):
        if not path.exists():
            failures.append(f"missing_source:{path}")
        elif card.get("passed") is not True:
            failures.append(f"source_failed:{card.get('stage_name', path.name)}")

    source_stage_names = {card.get("stage_name") for card in source_cards if card}
    source_stage_names.add(NAME)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in source_stage_names]
    for path, card in zip(SOURCES, source_cards):
        if card:
            rows.append(row_for(path, card))

    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {
            **AUTHORITY_CLOSED,
            "authority_rows": 0,
            "source_failures": failures,
            "sources_indexed": len([card for card in source_cards if card]),
            "registry_rows_before": len(registry.get("rows", [])),
            "registry_rows_after": len(rows) + 1,
            "bounded_decoder_argument_rows": (source_cards[-2].get("metrics") or {}).get("rows"),
            "bounded_decoder_argument_graph_nodes": (source_cards[-1].get("metrics") or {}).get("graph_nodes"),
            "bounded_decoder_argument_graph_edges": (source_cards[-1].get("metrics") or {}).get("graph_edges"),
            "bounded_decoder_training_loss_rows": (source_cards[-2].get("metrics") or {}).get("training_loss_rows"),
            "bounded_decoder_max_proxy_single": (source_cards[-2].get("metrics") or {}).get("max_proxy_single"),
            "bounded_decoder_max_proxy_combo": (source_cards[-2].get("metrics") or {}).get("max_proxy_combo"),
        },
        "decision": (
            "Reconciled registry and spine after bounded decoder argument controls were audited and graph-attached as a closed no-training objective."
            if not failures else "Registry/spine reconciliation failed; source summaries must be fixed first."
        ),
        "next_best_step": "Build a closed bounded decoder CE package gate that consumes audited argument controls, still without enabling decoder CE or runtime.",
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
    historical_failed_rows = sum(1 for row in rows if row.get("passed") is not True)
    registry["metrics"] = {
        **registry.get("metrics", {}),
        "latest_stage": STAGE,
        "latest_stage_name": NAME,
        "latest_stage_next_best_step": card["next_best_step"],
        "max_stage": STAGE,
        "registry_rows": len(rows),
        "historical_failed_rows": historical_failed_rows,
        "authority_counts": {key: 0 for key in AUTHORITY_CLOSED},
    }
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8800 Registry Spine Reconciliation After Bounded Decoder Controls",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Sources indexed: `{card['metrics']['sources_indexed']}`",
        f"Registry rows before: `{card['metrics']['registry_rows_before']}`",
        f"Registry rows after: `{card['metrics']['registry_rows_after']}`",
        f"Bounded decoder argument rows: `{card['metrics']['bounded_decoder_argument_rows']}`",
        f"Bounded decoder max proxy single: `{card['metrics']['bounded_decoder_max_proxy_single']}`",
        f"Bounded decoder max proxy combo: `{card['metrics']['bounded_decoder_max_proxy_combo']}`",
        "",
        "Authority remains closed: no mining, training, runtime, decoder CE, denoise CE, scoring, source/body emission, Gemma, controller merge, or promotion.",
        "",
    ]), encoding="utf-8")

    marker = "## Stage8797-8800 Bounded Decoder Argument Controls"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        append = "\n".join([
            "",
            marker,
            "",
            "Bounded decoder argument recovery has been reintroduced as a closed control objective, not as decoder CE training.",
            "",
            "- Stage8797 built a gate-complete no-authority bounded decoder argument controls manifest from the earlier neutral Stage8645 rows.",
            "- Stage8798 audited the controls: 504 rows, balanced labels, max proxy single 0.2857, max proxy combo 0.4286, zero training-loss rows, zero incomplete gate rows.",
            "- Stage8799 attached the objective to the central graph as `objective:bounded_decoder_arguments` with decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion closed.",
            "- Stage8800 reconciles the registry/spine so the current frontier is visible and does not get lost behind older recovery stages.",
            "",
            "Current frontier:",
            "",
            "```text",
            "source lineage/provenance",
            "-> contamination/leakage",
            "-> locked eval / drift canary",
            "-> schema / patch / coverage / flaky gates",
            "-> eval trace / skill registry / ngram / memory",
            "-> source-backed edit localization / patch operator / verifier repair",
            "-> query expansion and recovered-module integration audit",
            "-> bounded decoder argument controls",
            "-> closed bounded decoder CE package gate",
            "```",
            "",
            "Do not resume mining, decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, or promotion until the next bounded decoder CE package gate passes with the same recovered gate-status contract.",
            "",
        ])
        SPINE.write_text(spine_text.rstrip() + "\n" + append, encoding="utf-8")

    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
