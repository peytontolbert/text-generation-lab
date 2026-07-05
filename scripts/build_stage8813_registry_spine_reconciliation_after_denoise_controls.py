#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8813
NAME = "stage8813_registry_spine_reconciliation_after_denoise_controls"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_DENOISE_CONTROLS_STAGE8813.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8805_registry_spine_reconciliation_after_closed_ce_gate.json",
    ROOT / "runs/summaries/stage8810_output_repair_denoise_controls_manifest.json",
    ROOT / "runs/summaries/stage8811_output_repair_denoise_controls_shortcut_gate.json",
    ROOT / "runs/summaries/stage8812_output_repair_denoise_controls_graph_attachment.json",
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
            rows.append({
                "stage": int(card["stage"]),
                "stage_name": card["stage_name"],
                "passed": card.get("passed") is True,
                "path": str(path),
                "authority": AUTHORITY_CLOSED,
                "next_best_step": card.get("next_best_step"),
            })
    denoise = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    audit = cards[2].get("metrics", {}) if len(cards) > 2 else {}
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
            "output_repair_denoise_rows": denoise.get("rows"),
            "denoise_ce_eligible_now_rows": denoise.get("denoise_ce_eligible_now_rows"),
            "denoise_loss_rows": denoise.get("loss_rows"),
            "denoise_max_proxy_single": audit.get("max_proxy_single"),
            "denoise_max_proxy_combo": audit.get("max_proxy_combo"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled registry/spine after output repair/denoise controls; denoise CE remains closed and next recovery target is verifier-guided repair target materialization." if not failures else "Registry/spine reconciliation failed.",
        "next_best_step": "Continue source-backed decoder target materialization in the parallel track; after that, recover verifier-guided repair target materialization controls. Keep training/runtime/CE closed.",
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
        "# Stage8813 Registry Spine Reconciliation After Denoise Controls",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Output repair/denoise rows: `{card['metrics']['output_repair_denoise_rows']}`",
        f"Denoise CE eligible now rows: `{card['metrics']['denoise_ce_eligible_now_rows']}`",
        f"Denoise loss rows: `{card['metrics']['denoise_loss_rows']}`",
        f"Max proxy single: `{card['metrics']['denoise_max_proxy_single']}`",
        f"Max proxy combo: `{card['metrics']['denoise_max_proxy_combo']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8810-8813 Output Repair Denoise Controls"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Output repair/denoise is recovered as a closed control surface, not as denoise CE training.",
            "",
            "- Stage8810 rebuilt 360 output-repair/denoise control rows from the older neutral manifest with recovered gate-status fields and all losses closed.",
            "- Stage8811 audited shortcuts: repair signal is allowed semantic evidence, max proxy single/combo are 0.2083, and denoise CE eligible-now rows remain zero.",
            "- Stage8812 attached the objective to the central graph and recorded `objective:verifier_guided_repair_target_materialization` as the next missing recovery target after source-backed decoder target materialization.",
            "- Stage8813 updates the registry/spine frontier accordingly.",
            "",
            "Current boundary: denoise can classify bad-output repair routes and future masked-repair candidates, but denoise CE, decoder CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
