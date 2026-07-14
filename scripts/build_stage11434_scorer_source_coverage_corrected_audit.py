#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / "runs/local/artifacts"
SUMMARIES = ROOT / "runs/summaries"
STAGE = 11434
NAME = "stage11434_scorer_source_coverage_corrected_audit"
OUT = ART / NAME
SUMMARY = OUT / "scorer_source_coverage_corrected_audit.json"

SOURCE_AUDIT = ART / "stage11433_selected_test_rust_scorer_source_audit"
SOURCE_SUMMARY = SOURCE_AUDIT / "selected_test_rust_scorer_source_audit.json"
SOURCES = [
    "encoder_option_retrieval",
    "encoder_option_retrieval_conditioned",
    "encoder_option_retrieval_evidence_role_map",
    "encoder_option_retrieval_dynamic_productized",
    "encoder_option_retrieval_evidence_judgment_head",
    "encoder_option_retrieval_evidence_ledger_head",
    "encoder_option_retrieval_verifier_conditioned",
    "encoder_option_retrieval_semantic_candidate_head",
]
SPLITS = ["validation", "strict", "reserved"]


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text()) if path.exists() else {}


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")


def corrected_card_metrics(card: dict[str, Any]) -> dict[str, Any]:
    rows = int(card.get("rows") or 0)
    constrained = int(card.get("constrained_choice_rows") or 0)
    row_cards = list(card.get("row_cards") or [])
    correct = sum(1 for row in row_cards if row.get("constrained_choice_match") is True)
    misses = [
        {
            "row_id": row.get("row_id"),
            "target_text": row.get("target_text"),
            "bounded_choice_target_label": row.get("bounded_choice_target_label"),
            "constrained_choice_match": row.get("constrained_choice_match"),
            "constrained_choice_top1_label": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in row_cards
        if row.get("constrained_choice_match") is not True
    ]
    return {
        "rows": rows,
        "constrained_choice_rows": constrained,
        "coverage": (constrained / rows) if rows else None,
        "reported_accuracy_on_scored_rows": card.get("constrained_choice_top1_accuracy"),
        "correct": correct,
        "coverage_corrected_accuracy": (correct / rows) if rows else None,
        "unscored_rows": max(0, rows - constrained),
        "miss_or_unscored_rows": misses,
    }


def main() -> None:
    source_summary = read_json(SOURCE_SUMMARY)
    corrected: dict[str, Any] = {}
    for source in SOURCES:
        corrected[source] = {}
        for split in SPLITS:
            path = SOURCE_AUDIT / source / f"bounded_choice_eval_audit_{split}.json"
            corrected[source][split] = corrected_card_metrics(read_json(path))

    deployable = {}
    for source, splits in corrected.items():
        validation = splits["validation"]
        strict = splits["strict"]
        reserved = splits["reserved"]
        ok = (
            validation["coverage"] == 1.0
            and strict["coverage"] == 1.0
            and reserved["coverage"] == 1.0
            and (validation["coverage_corrected_accuracy"] or 0.0) >= (20 / 23)
            and (strict["coverage_corrected_accuracy"] or 0.0) >= (22 / 23)
            and (reserved["coverage_corrected_accuracy"] or 0.0) > 0.5
        )
        if ok:
            deployable[source] = splits

    summary = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "no_existing_scorer_source_promoted_after_coverage_correction" if not deployable else "coverage_corrected_scorer_candidate_found",
        "claim_scope": [
            "Correct Stage11433 scorer-source comparison for scorer coverage.",
            "Any row without constrained-choice output is counted as not solved for promotion purposes.",
            "This prevents falsely treating partial scorer coverage as high accuracy.",
        ],
        "source_artifacts": {
            "stage11433_summary": rel(SOURCE_SUMMARY),
        },
        "baseline_stage11433_decision": source_summary.get("decision"),
        "coverage_corrected_results": corrected,
        "deployable_candidates": deployable,
        "decision_basis": [
            "encoder_option_retrieval_evidence_ledger_head reported high reserved accuracy because it scored only one reserved row.",
            "A deployable scorer must cover all validation, strict, and reserved rows while preserving canary scores and improving reserved residuals.",
            "The next useful implementation is a real semantic scorer objective/head with full row coverage, not inference-side scorer routing.",
        ],
        "outputs": {"summary": rel(SUMMARY)},
    }
    write_json(SUMMARY, summary)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    compact = {
        "decision": summary["decision"],
        "deployable_candidates": list(deployable.keys()),
        "coverage_corrected": {
            source: {
                split: {
                    "coverage": metrics["coverage"],
                    "coverage_corrected_accuracy": metrics["coverage_corrected_accuracy"],
                    "reported_accuracy_on_scored_rows": metrics["reported_accuracy_on_scored_rows"],
                    "unscored_rows": metrics["unscored_rows"],
                }
                for split, metrics in splits.items()
            }
            for source, splits in corrected.items()
        },
    }
    print(json.dumps(compact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
