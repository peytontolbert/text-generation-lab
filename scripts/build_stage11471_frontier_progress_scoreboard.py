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

STAGE = 11471
NAME = "stage11471_frontier_progress_scoreboard"
OUT = ART / NAME
SUMMARY = OUT / "frontier_progress_scoreboard.json"

FRONTIER_DECISION = ART / "stage11462_post_rust_breadth_frontier_decision/post_rust_breadth_frontier_decision.json"
HARNESS_RESULT = ART / "stage11467_selected_runtime_harness_result_audit/selected_runtime_harness_result_audit.json"
PROMOTION_GATE = ART / "stage11468_selected_runtime_harness_promotion_gate_audit/selected_runtime_harness_promotion_gate_audit.json"
SUCCESSOR_INVENTORY = ART / "stage11469_source_heldout_harness_successor_inventory/source_heldout_harness_successor_inventory.json"
MATERIALIZATION_REQUEST = ART / "stage11470_harness_successor_materialization_request/harness_successor_materialization_request.json"

BASE_AUDIT_DIR = ART / "stage11445_targeted_residual_role_support_postrun_audit"
SCORE_FILES = {
    "filtered_strict": BASE_AUDIT_DIR / "bounded_choice_eval_audit_filtered_strict_encoder_option_retrieval.json",
    "filtered_validation": BASE_AUDIT_DIR / "bounded_choice_eval_audit_filtered_validation_encoder_option_retrieval.json",
    "old_canary_strict": BASE_AUDIT_DIR / "bounded_choice_eval_audit_old_canary_strict_encoder_option_retrieval.json",
    "old_canary_validation": BASE_AUDIT_DIR / "bounded_choice_eval_audit_old_canary_validation_encoder_option_retrieval.json",
    "residual_bank": BASE_AUDIT_DIR / "bounded_choice_eval_audit_residual_bank_encoder_option_retrieval.json",
}


def now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def card_metric(path: Path) -> dict[str, Any]:
    card = load_json(path)
    row_cards = [row for row in card.get("row_cards") or [] if isinstance(row, dict)]
    misses = [
        {
            "row_id": row.get("row_id"),
            "target": row.get("bounded_choice_target_label"),
            "predicted": row.get("constrained_choice_top1_label"),
            "full_vocab_top1_text": row.get("full_vocab_top1_text"),
            "target_rank_full_vocab": row.get("target_rank_full_vocab"),
        }
        for row in row_cards
        if row.get("constrained_choice_match") is not True
    ]
    return {
        "path": rel(path),
        "rows": card.get("rows"),
        "correct": card.get("constrained_choice_correct"),
        "coverage": card.get("constrained_choice_coverage"),
        "coverage_corrected_accuracy": card.get("constrained_choice_coverage_corrected_top1_accuracy"),
        "misses": misses,
    }


def promotion_gates(scores: dict[str, dict[str, Any]]) -> dict[str, bool]:
    return {
        "old_canary_strict_23_of_23": scores["old_canary_strict"].get("correct") == 23
        and scores["old_canary_strict"].get("rows") == 23,
        "filtered_strict_22_of_22": scores["filtered_strict"].get("correct") == 22
        and scores["filtered_strict"].get("rows") == 22,
        "filtered_validation_at_least_20_of_22": (scores["filtered_validation"].get("correct") or 0) >= 20
        and scores["filtered_validation"].get("rows") == 22,
        "old_canary_validation_at_least_21_of_23": (scores["old_canary_validation"].get("correct") or 0) >= 21
        and scores["old_canary_validation"].get("rows") == 23,
        "residual_bank_at_least_6_of_10": (scores["residual_bank"].get("correct") or 0) >= 6
        and scores["residual_bank"].get("rows") == 10,
        "residual_full_coverage": scores["residual_bank"].get("coverage") == 1.0,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frontier = load_json(FRONTIER_DECISION)
    harness = load_json(HARNESS_RESULT)
    promotion = load_json(PROMOTION_GATE)
    successor = load_json(SUCCESSOR_INVENTORY)
    materialization = load_json(MATERIALIZATION_REQUEST)

    selected_scores = {name: card_metric(path) for name, path in SCORE_FILES.items()}
    gates = promotion_gates(selected_scores)
    real_model_improvement_ready = all(gates.values())
    frontier_score = {
        "selected_frontier": frontier.get("selected_frontier"),
        "preservation": {
            "old_canary_strict": {
                "correct": selected_scores["old_canary_strict"]["correct"],
                "rows": selected_scores["old_canary_strict"]["rows"],
            },
            "filtered_strict": {
                "correct": selected_scores["filtered_strict"]["correct"],
                "rows": selected_scores["filtered_strict"]["rows"],
            },
            "filtered_validation": {
                "correct": selected_scores["filtered_validation"]["correct"],
                "rows": selected_scores["filtered_validation"]["rows"],
            },
            "old_canary_validation": {
                "correct": selected_scores["old_canary_validation"]["correct"],
                "rows": selected_scores["old_canary_validation"]["rows"],
            },
        },
        "frontier": {
            "residual_bank": {
                "correct": selected_scores["residual_bank"]["correct"],
                "rows": selected_scores["residual_bank"]["rows"],
                "misses": selected_scores["residual_bank"]["misses"],
            },
            "residual_plateau": selected_scores["residual_bank"]["correct"] == 5,
        },
        "system": {
            "harness_writeback_complete": bool(harness.get("passed")),
            "harness_hundred_m_accuracy": (harness.get("metrics") or {}).get("hundred_m_accuracy"),
            "harness_gemma12b_accuracy": (harness.get("metrics") or {}).get("gemma12b_accuracy"),
            "harness_claim_promotion_ready": bool(promotion.get("promotion_ready")),
            "harness_promotion_blockers": promotion.get("promotion_blockers"),
        },
        "generalization": {
            "source_heldout_successor_admitted_rows": (successor.get("metrics") or {}).get("admitted_rows"),
            "source_heldout_successor_ready": successor.get("decision") == "source_heldout_harness_successor_ready",
            "materialization_required": materialization.get("decision")
            == "materialization_required_before_successor_harness_probe",
        },
    }

    rejected = frontier.get("rejected_runtimes") or {}
    rejected_table = []
    for name, record in rejected.items():
        metrics = record.get("product_metrics") or {}
        gates_record = record.get("promotion_gates") or {}
        rejected_table.append(
            {
                "stage": name,
                "decision": record.get("decision"),
                "weights_sha256": record.get("weights_sha256"),
                "metrics": metrics,
                "why_not_progress": [
                    gate for gate, passed in gates_record.items() if passed is not True
                ],
            }
        )

    next_probe_contract = {
        "allowed_target_metric": "residual_bank",
        "minimum_promotion_thresholds": {
            "old_canary_strict": "23/23",
            "filtered_strict": "22/22",
            "filtered_validation": ">=20/22",
            "old_canary_validation": ">=21/23",
            "residual_bank": ">=6/10",
            "coverage": "1.0 on bounded-choice scored rows",
            "product_scorer": "encoder_option_retrieval",
        },
        "disallowed_as_promotion": [
            "decoder_first_step only gains",
            "semantic_candidate_head only gains",
            "support package with residual unchanged at 5/10",
            "strict/canary gains with residual unchanged",
            "residual gains with old canary or filtered strict regression",
        ],
        "recommended_next_experiment": (
            "A non-promotable diagnostic may train directly against residual rows to test whether base encoder_option_retrieval can move. "
            "A promotable follow-up must rebuild the same residual concepts from disjoint roots before claiming frontier progress."
        ),
    }

    payload = {
        "stage": STAGE,
        "stage_name": NAME,
        "created_at_utc": now(),
        "passed": True,
        "decision": "selected_frontier_preserved_but_residual_frontier_not_lifted",
        "selected_frontier_status": "preservation_and_harness_win_only"
        if not real_model_improvement_ready
        else "promotion_candidate",
        "scoreboards": {
            "preservation": frontier_score["preservation"],
            "frontier": frontier_score["frontier"],
            "generalization": frontier_score["generalization"],
            "system": frontier_score["system"],
        },
        "promotion_gates": gates,
        "real_model_improvement_ready": real_model_improvement_ready,
        "rejected_diagnostics": rejected_table,
        "progress_accounting_rules": [
            "A stage is model progress only if it improves residual or sealed heldout while preserving canary/filtered strict and validation gates.",
            "Harness/writeback progress is system progress, not model-frontier progress unless paired with residual or sealed-heldout lift.",
            "Data inventory/materialization progress is useful but not a model improvement until a selected scorer improves on protected metrics.",
            "The legacy Rust singleton canary row cannot be counted as Rust verifier discrimination.",
        ],
        "next_probe_contract": next_probe_contract,
        "source_artifacts": {
            "frontier_decision": rel(FRONTIER_DECISION),
            "harness_result": rel(HARNESS_RESULT),
            "promotion_gate": rel(PROMOTION_GATE),
            "successor_inventory": rel(SUCCESSOR_INVENTORY),
            "materialization_request": rel(MATERIALIZATION_REQUEST),
            "score_files": {name: rel(path) for name, path in SCORE_FILES.items()},
        },
        "outputs": {"summary": rel(SUMMARY)},
    }

    write_json(SUMMARY, payload)
    SUMMARIES.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SUMMARY, SUMMARIES / f"{NAME}.json")
    print(
        json.dumps(
            {
                "decision": payload["decision"],
                "selected_frontier_status": payload["selected_frontier_status"],
                "promotion_gates": gates,
                "residual": frontier_score["frontier"]["residual_bank"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
