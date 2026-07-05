#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8819
NAME = "stage8819_registry_spine_reconciliation_after_eval_strict_gap"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_EVAL_STRICT_GAP_STAGE8819.md"
SPINE = ROOT / "docs" / "MODEL_STACK_SPINE.md"
SOURCES = [
    ROOT / "runs/summaries/stage8816_registry_spine_reconciliation_after_split_dedup_ce_selection.json",
    ROOT / "runs/summaries/stage8817_eval_strict_unique_target_gap_manifest.json",
    ROOT / "runs/summaries/stage8818_eval_strict_unique_target_gap_graph_attachment.json",
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
            rows.append({"stage": int(card["stage"]), "stage_name": card["stage_name"], "passed": card.get("passed") is True, "path": str(path), "authority": AUTHORITY_CLOSED, "next_best_step": card.get("next_best_step")})
    gap = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    graph = cards[2].get("metrics", {}) if len(cards) > 2 else {}
    card = {
        "stage": STAGE,
        "stage_name": NAME,
        "passed": not failures,
        "authority": AUTHORITY_CLOSED,
        "metrics": {**AUTHORITY_CLOSED, "authority_rows": 0, "source_failures": failures, "sources_indexed": len([c for c in cards if c]), "registry_rows_before": len(registry.get("rows", [])), "registry_rows_after": len(rows) + 1, "gap_rows": gap.get("rows"), "eval_gap_rows": (gap.get("split_counts") or {}).get("eval"), "strict_gap_rows": (gap.get("split_counts") or {}).get("strict"), "loss_rows": gap.get("loss_rows"), "decoder_ce_eligible_now_rows": gap.get("decoder_ce_eligible_now_rows"), "graph_nodes": graph.get("graph_nodes"), "graph_edges": graph.get("graph_edges")},
        "decision": "Reconciled eval/strict unique target gap into registry/spine. Bounded decoder CE remains blocked until split-unique eval/strict targets or heldout evaluation are recovered.",
        "next_best_step": "Design split-unique eval/strict target materialization or heldout non-CE evaluation package. Keep CE/runtime/model execution closed.",
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    rows.append({"stage": STAGE, "stage_name": NAME, "passed": card["passed"], "path": str(SUMMARY), "authority": AUTHORITY_CLOSED, "next_best_step": card["next_best_step"]})
    rows = sorted(rows, key=lambda row: (int(row.get("stage", -1)), row.get("stage_name", "")))
    registry["rows"] = rows
    registry["passed"] = not failures
    registry["metrics"] = {**registry.get("metrics", {}), "latest_stage": STAGE, "latest_stage_name": NAME, "latest_stage_next_best_step": card["next_best_step"], "max_stage": STAGE, "registry_rows": len(rows), "historical_failed_rows": sum(1 for row in rows if row.get("passed") is not True), "authority_counts": {key: 0 for key in AUTHORITY_CLOSED}}
    REGISTRY.write_text(json.dumps(registry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    DOC.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(card, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    DOC.write_text("\n".join(["# Stage8819 Registry Spine Reconciliation After Eval/Strict Gap", "", f"Passed: `{card['passed']}`", "", f"Gap rows: `{card['metrics']['gap_rows']}`", f"Eval gap rows: `{card['metrics']['eval_gap_rows']}`", f"Strict gap rows: `{card['metrics']['strict_gap_rows']}`", "", "The frontier is now the eval/strict target uniqueness problem, not source-backed target materialization itself.", ""]), encoding="utf-8")
    marker = "## Stage8817-8819 Eval/Strict Unique Target Gap"
    spine_text = SPINE.read_text(encoding="utf-8") if SPINE.exists() else ""
    if marker not in spine_text:
        SPINE.write_text(spine_text.rstrip() + "\n\n" + "\n".join([marker, "", "The split-deduped CE candidate path revealed that train candidates can be selected safely, but eval/strict target hashes duplicate train target hashes. Stage8817 materialized this as 240 explicit gap rows: 120 eval and 120 strict. Stage8818 attached the gap to the graph, and Stage8819 reconciles it into the registry/spine.", "", "Current next step: design split-unique eval/strict target materialization or a heldout non-CE evaluation package. Decoder CE, denoise CE, runtime, source/body emission, Gemma, scoring, controller merge, and promotion remain closed.", ""]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
