#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8875
NAME = "stage8875_registry_spine_reconciliation_after_verifier_guided_targets"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_VERIFIER_GUIDED_TARGETS_STAGE8875.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8872_verifier_guided_repair_target_materialization_controls.json",
    ROOT / "runs/summaries/stage8873_verifier_guided_repair_target_materialization_audit.json",
    ROOT / "runs/summaries/stage8874_verifier_guided_repair_target_materialization_graph_attachment.json",
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
    names = {NAME}
    names.update(card_src.get("stage_name") for card_src in cards if card_src)
    rows = [row for row in registry.get("rows", []) if row.get("stage_name") not in names]
    for path, card_src in zip(SOURCES, cards):
        if card_src:
            rows.append({
                "stage": int(card_src["stage"]),
                "stage_name": card_src["stage_name"],
                "passed": card_src.get("passed") is True,
                "path": str(path),
                "authority": AUTHORITY_CLOSED,
                "next_best_step": card_src.get("next_best_step"),
            })
    build = cards[0].get("metrics", {}) if cards else {}
    audit = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    attach = cards[2].get("metrics", {}) if len(cards) > 2 else {}
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
            "materialized_rows": build.get("materialized_rows"),
            "target_store_rows": build.get("target_store_rows"),
            "target_text_copied_to_manifest_rows": audit.get("target_text_copied_to_manifest_rows"),
            "denoise_ce_eligible_now_rows": audit.get("denoise_ce_eligible_now_rows"),
            "runtime_verifier_execution_eligible_now_rows": audit.get("runtime_verifier_execution_eligible_now_rows"),
            "graph_nodes": attach.get("graph_nodes"),
            "graph_edges": attach.get("graph_edges"),
            "training_authorized": False,
            "denoise_ce_authorized": False,
            "runtime_verifier_execution_authorized": False,
        },
        "decision": "Reconciled verifier-guided repair target materialization controls into registry/spine.",
        "next_best_step": "Continue with eval/strict unique target materialization or packet-schema readiness blockers; keep model execution, denoise CE, decoder CE, runtime, and mining closed.",
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
        "# Stage8875 Registry Spine Reconciliation After Verifier-Guided Targets",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Materialized rows: `{card['metrics']['materialized_rows']}`",
        f"Target-store rows: `{card['metrics']['target_store_rows']}`",
        f"Target text copied to manifest rows: `{card['metrics']['target_text_copied_to_manifest_rows']}`",
        f"Denoise CE eligible now rows: `{card['metrics']['denoise_ce_eligible_now_rows']}`",
        f"Runtime verifier execution eligible now rows: `{card['metrics']['runtime_verifier_execution_eligible_now_rows']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8872-8875 Verifier-Guided Repair Target Materialization"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Verifier-guided repair target materialization is now recovered as a closed-boundary target-store control.",
            "",
            "- Stage8872 materializes repair targets from audited source-backed verifier-repair rows into a separate target store.",
            "- Stage8873 audits target refs, hashes, leakage, authority, and closed denoise/runtime gates.",
            "- Stage8874 attaches the resolved objective to the central graph.",
            "- Stage8875 reconciles registry/spine.",
            "",
            "This does not authorize denoise CE, runtime verifier execution, decoder CE, model execution, source/body emission, Gemma, harness, scoring, mining, or promotion.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
