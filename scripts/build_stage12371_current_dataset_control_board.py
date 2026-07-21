#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12371_current_dataset_control_board"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
HONEST_LEDGER = ROOT / "runs/summaries/stage12370_full_selected_test_anti_collapse_ledger_v8.json"
POLICY = ROOT / "runs/summaries/stage12364_diversity_weighted_admission_policy.json"
CANDLE_BLOCKER = ROOT / "runs/summaries/stage12365_candle_rust_display_verifier_blocker.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = read_json(HONEST_LEDGER)
    policy = read_json(POLICY)
    candle = read_json(CANDLE_BLOCKER)
    control = {
        "stage": STAGE,
        "decision": "current_dataset_control_board_ready",
        "training_allowed": False,
        "claim_boundary": "Control board only. No rows admitted.",
        "selected_current_ledger_ref": str(HONEST_LEDGER),
        "selected_policy_ref": str(POLICY),
        "current_honest_train_support_tasks": ledger.get("current_admitted_train_support_tasks"),
        "remaining_gap_to_500": ledger.get("remaining_gap_to_500"),
        "language_counts": ledger.get("language_counts"),
        "task_family_counts": ledger.get("task_family_or_record_type_counts"),
        "selected_test_rows_admitted_after_audit": ledger.get("selected_test_rows_admitted_after_audit"),
        "selected_test_rows_quarantined_after_audit": ledger.get("selected_test_rows_quarantined_after_audit"),
        "stale_counts_not_authoritative": [
            "stage12363_combined_train_support_ledger_v6:176",
            "stage12366_selected_test_semantic_collapse_audit:168",
            "stage12369_combined_train_support_ledger_v7:178",
        ],
        "active_policy_summary": {
            "org_caps_are_not_hard_blocks": True,
            "diversity_weighting_required": True,
            "MCP_core_train_support_reconsiderable": ((policy.get("weighted_warnings_not_hard_rejects") or {}).get("MCP_core") is not None),
            "Open_SWE_requires_safe_semantic_extraction": ((policy.get("weighted_warnings_not_hard_rejects") or {}).get("Open_SWE") is not None),
        },
        "known_blocked_candidates": {
            "candle_display_tests": candle.get("blocked_reasons"),
        },
        "next_admission_focus": [
            "re-render collapsed selected-test roots with task-specific target vocabularies",
            "execute fresh non-web Rust/C++ focused verifiers",
            "move MCP only after non-web batch or when using diversity-weighted web accounting",
            "transform Open-SWE QC through internal episode graph extraction, never direct admission",
        ],
    }
    (OUT / "current_dataset_control_board.json").write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
