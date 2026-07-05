#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = 8815
NAME = "stage8815_registry_spine_reconciliation_after_transformer_path_index"
REGISTRY = ROOT / "runs/local/artifacts/reconstructed_stage_registry.json"
SUMMARY = ROOT / "runs/summaries" / f"{NAME}.json"
DOC = ROOT / "docs" / "REGISTRY_SPINE_RECONCILIATION_AFTER_TRANSFORMER_PATH_STAGE8815.md"
SOURCES = [
    ROOT / "runs/summaries/stage8809_registry_spine_reconciliation_after_target_materialization.json",
    ROOT / "runs/summaries/stage8813_registry_spine_reconciliation_after_denoise_controls.json",
    ROOT / "runs/summaries/stage8814_transformer_path_study_graph_attachment.json",
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
    target = cards[0].get("metrics", {}) if cards else {}
    denoise = cards[1].get("metrics", {}) if len(cards) > 1 else {}
    transformer = cards[2].get("metrics", {}) if len(cards) > 2 else {}
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
            "target_materialized_rows": target.get("materialized_rows"),
            "target_decoder_ce_eligible_now_rows": target.get("decoder_ce_eligible_now_rows"),
            "denoise_rows": denoise.get("output_repair_denoise_rows"),
            "denoise_ce_eligible_now_rows": denoise.get("denoise_ce_eligible_now_rows"),
            "transformer_required_files_present": transformer.get("required_files_present"),
            "transformer_required_files_total": transformer.get("required_files_total"),
            "graph_nodes": transformer.get("graph_nodes"),
            "graph_edges": transformer.get("graph_edges"),
        },
        "decision": "Reconciled registry/spine after transformer-path graph index; target materialization, denoise controls, and transformer study path are now visible together.",
        "next_best_step": "Build split-deduped closed CE candidate selection from target store while using transformer-path shape/loss telemetry as the future debug checklist; keep execution/training closed.",
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
        "# Stage8815 Registry Spine Reconciliation After Transformer Path Index",
        "",
        f"Passed: `{card['passed']}`",
        "",
        f"Target materialized rows: `{card['metrics']['target_materialized_rows']}`",
        f"Target decoder CE eligible now rows: `{card['metrics']['target_decoder_ce_eligible_now_rows']}`",
        f"Denoise rows: `{card['metrics']['denoise_rows']}`",
        f"Denoise CE eligible now rows: `{card['metrics']['denoise_ce_eligible_now_rows']}`",
        f"Transformer required files present: `{card['metrics']['transformer_required_files_present']}/{card['metrics']['transformer_required_files_total']}`",
        "",
        "Authority remains closed.",
        "",
    ]), encoding="utf-8")
    print(json.dumps(card, indent=2, sort_keys=True))
    raise SystemExit(0 if card["passed"] else 1)

if __name__ == "__main__":
    main()
