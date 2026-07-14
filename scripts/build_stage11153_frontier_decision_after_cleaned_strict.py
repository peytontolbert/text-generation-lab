#!/usr/bin/env python3
"""Record the current cleaned-strict frontier and data-quality next steps."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "runs/local/artifacts/stage11153_frontier_decision_after_cleaned_strict"

INPUTS = {
    "cleaned_strict_comparison": ROOT
    / "runs/local/artifacts/stage11150_cleaned_strict_100m_vs_gemma_comparison/cleaned_strict_100m_vs_gemma_comparison.json",
    "residual_packet_repair_audit": ROOT
    / "runs/local/artifacts/stage11143_residual_packet_repair_audit/residual_packet_repair_audit.json",
    "python_verifier_ledger_audit": ROOT
    / "runs/local/artifacts/stage11151_python_verifier_candidate_ledger_audit/python_verifier_candidate_ledger_audit.json",
    "explicit_verifier_supply_audit": ROOT
    / "runs/local/artifacts/stage11152_explicit_verifier_transition_supply_audit/explicit_verifier_transition_supply_audit.json",
    "singleton_quarantine": ROOT
    / "runs/local/artifacts/stage11146_singleton_strict_quarantine_successor/singleton_strict_quarantine_successor.json",
}


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    data = {name: load(path) for name, path in INPUTS.items()}
    comparison = data["cleaned_strict_comparison"]
    packet_audit = data["residual_packet_repair_audit"]
    ledger_audit = data["python_verifier_ledger_audit"]
    supply_audit = data["explicit_verifier_supply_audit"]
    quarantine = data["singleton_quarantine"]

    summary = {
        "stage": 11153,
        "stage_name": "frontier_decision_after_cleaned_strict",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_artifacts": {
            key: str(path.relative_to(ROOT)) for key, path in INPUTS.items()
        },
        "current_cleaned_strict_frontier": {
            "rows": comparison["overall"]["rows"],
            "hundred_m_correct": comparison["overall"]["hundred_m_correct"],
            "hundred_m_accuracy": comparison["overall"]["hundred_m_accuracy"],
            "gemma12b_correct": comparison["overall"]["gemma12b_correct"],
            "gemma12b_accuracy": comparison["overall"]["gemma12b_accuracy"],
            "delta": comparison["overall"]["delta"],
            "coverage": comparison["coverage"],
            "by_language": comparison["by_language"],
            "hundred_m_mismatches": comparison["hundred_m_mismatches"],
        },
        "eval_hygiene": {
            "singleton_strict_rows_quarantined": quarantine["metrics"]["strict_singleton_quarantined"],
            "quarantined_rows": quarantine["quarantined_rows"],
            "strict_rows_after_quarantine": quarantine["metrics"]["strict_rows_after"],
            "strict_language_counts_after": quarantine["metrics"]["strict_by_language_after"],
        },
        "data_readiness": {
            "residual_packets_admitted_now": packet_audit["metrics"]["admitted_now"],
            "residual_packets_repairable_after_review": packet_audit["metrics"]["repairable_after_review"],
            "python_verifier_candidates_admitted": ledger_audit["metrics"]["admission_counts"].get(
                "admit_for_transition_review", 0
            ),
            "explicit_transition_supply_accepted": supply_audit["candidate_metrics"]["accepted_rows"],
            "explicit_transition_supply_rejected_reasons": supply_audit["candidate_metrics"][
                "rejected_reason_counts"
            ],
        },
        "decision": "do_not_train_until_new_residual_rows_are_admitted",
        "claim_scope": [
            "Cleaned strict standalone comparison currently favors 100M over Gemma3 12B on all represented language slices.",
            "This is still a compact reviewed bounded-choice maintainer eval, not a broad freeform software-maintenance or full-product harness result.",
            "The remaining 100M miss is the Python code_assist verifier_outcome_semantic_transition row, where Gemma is correct.",
            "No new root-disjoint explicit verifier-transition supply is currently admitted for training.",
        ],
        "required_next_materialization": [
            "Build fresh Python verifier-transition roots with real verifier target ledgers and no target-only leakage.",
            "Materialize Rust selected-test/verifier anchors before using Rust repair packets.",
            "Replace or replenish the quarantined Rust singleton verifier row with a multi-option verifier row.",
            "Do not run another support probe from stage11145 or stage11152 because both are non-admitted.",
        ],
        "outputs": {
            "summary_json": str((OUT_DIR / "frontier_decision_after_cleaned_strict.json").relative_to(ROOT)),
        },
    }
    (OUT_DIR / "frontier_decision_after_cleaned_strict.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
