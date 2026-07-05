#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8809
NAME = "stage8809_registry_spine_reconciliation_after_target_materialization"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_TARGET_MATERIALIZATION_STAGE8809.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8805_registry_spine_reconciliation_after_closed_ce_gate.json",
    ROOT / "runs/summaries/stage8806_source_backed_decoder_target_materialization_controls.json",
    ROOT / "runs/summaries/stage8807_source_backed_decoder_target_materialization_audit.json",
    ROOT / "runs/summaries/stage8808_source_backed_decoder_target_materialization_graph_attachment.json",
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
    mat = cards[1].get("metrics", {}) if len(cards) > 1 else {}
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
            "materialized_rows": mat.get("materialized_rows"),
            "target_store_rows": mat.get("target_store_rows"),
            "blocked_rows": mat.get("blocked_rows"),
            "decoder_ce_eligible_now_rows": mat.get("decoder_ce_eligible_now_rows"),
            "training_loss_rows": mat.get("training_loss_rows"),
            "target_text_copied_to_manifest_rows": audit.get("target_text_copied_to_manifest_rows"),
            "cross_split_duplicate_target_hashes": audit.get("cross_split_duplicate_target_hashes"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled registry/spine after source-backed target materialization. Decoder CE remains closed pending split-deduped candidate selection and explicit authorization." if not failures else "Registry/spine reconciliation after target materialization failed.",
        "next_best_step": "Build split-deduped closed CE candidate selection from target store; keep decoder CE/runtime/source-body/Gemma/scoring closed.",
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8809 Registry Spine Reconciliation After Target Materialization",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Materialized rows: `{card['metrics']['materialized_rows']}`",
        f"Target-store rows: `{card['metrics']['target_store_rows']}`",
        f"CE eligible now rows: `{card['metrics']['decoder_ce_eligible_now_rows']}`",
        f"Cross-split duplicate target hashes: `{card['metrics']['cross_split_duplicate_target_hashes']}`",
        "",
        "Authority remains closed. The next step is split-deduped closed CE candidate selection, not training.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8806-8809 Source-Backed Decoder Target Materialization"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Recovered source-backed decoder target materialization as a closed control layer. Stage8806 materialized 360 bounded target texts into a separate target-store artifact and kept 144 rows blocked. Stage8807 audited that target text is not copied into the manifest/model input, target refs and hashes match, authority and loss rows are zero, and CE eligibility remains zero. Stage8808 attached this to the central graph.",
            "",
            "Important blocker discovered: 120 target hashes repeat across train/eval/strict, covering all 360 target-store rows. This is not a materialization failure while CE is closed, but it blocks future CE selection until split dedup or split-specific target materialization is designed.",
            "",
            "Current next step: build split-deduped closed CE candidate selection from the target store. Decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
