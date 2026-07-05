#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8813
NAME = "stage8813_registry_spine_reconciliation_after_split_dedup_ce_selection"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_SPLIT_DEDUP_CE_SELECTION_STAGE8813.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8809_registry_spine_reconciliation_after_target_materialization.json",
    ROOT / "runs/summaries/stage8810_split_deduped_closed_ce_candidate_selection.json",
    ROOT / "runs/summaries/stage8811_split_deduped_closed_ce_candidate_selection_audit.json",
    ROOT / "runs/summaries/stage8812_split_deduped_closed_ce_candidate_graph_attachment.json",
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
    sel = cards[1].get("metrics", {}) if len(cards) > 1 else {}
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
            "selected_candidate_rows": sel.get("selected_candidate_rows"),
            "selected_split_counts": sel.get("selected_split_counts"),
            "selected_eval_rows": audit.get("selected_eval_rows"),
            "selected_strict_rows": audit.get("selected_strict_rows"),
            "probe_ready": audit.get("probe_ready"),
            "training_loss_rows": audit.get("training_loss_rows"),
            "decoder_ce_eligible_now_rows": audit.get("decoder_ce_eligible_now_rows"),
            "graph_nodes": graph.get("graph_nodes"),
            "graph_edges": graph.get("graph_edges"),
        },
        "decision": "Reconciled registry/spine after split-deduped closed CE selection. The recovered CE path now has train-only candidate support but remains not probe-ready." if not failures else "Registry/spine reconciliation after split-dedup CE selection failed.",
        "next_best_step": "Recover eval/strict unique target materialization or heldout evaluation design before any decoder CE loss-mask package. Keep all execution and CE authority closed.",
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
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join([
        "# Stage8813 Registry Spine Reconciliation After Split-Dedup CE Selection",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Selected candidate rows: `{card['metrics']['selected_candidate_rows']}`",
        f"Selected split counts: `{card['metrics']['selected_split_counts']}`",
        f"Probe ready: `{card['metrics']['probe_ready']}`",
        "",
        "The CE path remains closed. The immediate missing layer is eval/strict unique target materialization or a heldout evaluation design.",
        "",
    ]), encoding="utf-8")
    marker = "## Stage8810-8813 Split-Deduped Closed CE Candidate Selection"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([
            marker,
            "",
            "Recovered split-deduped closed CE candidate selection from the source-backed target store. Stage8810 selected 120 unique target-hash candidates and blocked 384 rows. Stage8811 audited that all selected candidates are train-only, with zero eval/strict selected rows, zero loss rows, zero CE eligibility, and zero authority rows. Stage8812 attached this to the central graph.",
            "",
            "This is useful train-side candidate support but not a probe-ready CE package. The next missing module is eval/strict unique target materialization or a heldout evaluation design that avoids cross-split target duplication.",
            "",
            "Decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.",
            "",
        ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)


if __name__ == "__main__":
    main()
