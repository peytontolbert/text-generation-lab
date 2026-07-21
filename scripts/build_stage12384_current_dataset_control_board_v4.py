#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12384_current_dataset_control_board_v4"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
LEDGER = ROOT / "runs/summaries/stage12383_combined_train_support_ledger_v14.json"
POLICY = ROOT / "runs/summaries/stage12364_diversity_weighted_admission_policy.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = read_json(LEDGER)
    policy = read_json(POLICY)
    control = {
        "stage": STAGE,
        "decision": "current_dataset_control_board_v4_ready",
        "training_allowed": False,
        "claim_boundary": "Control board only. No rows admitted.",
        "selected_current_ledger_ref": str(LEDGER),
        "selected_policy_ref": str(POLICY),
        "current_honest_train_support_tasks": ledger.get("current_admitted_train_support_tasks"),
        "remaining_gap_to_500": ledger.get("remaining_gap_to_500"),
        "language_counts": ledger.get("language_counts"),
        "task_family_counts": ledger.get("task_family_or_record_type_counts"),
        "selected_test_quality_gates": {
            "raw_command_rows": ledger.get("selected_test_raw_command_rows_should_be_zero"),
            "risky_claim_counts": ledger.get("risky_claim_counts_should_be_zero"),
            "anti_collapse_failures": ledger.get("anti_collapse_failures_should_be_empty"),
        },
        "stale_counts_not_authoritative": [
            "stage12363_combined_train_support_ledger_v6:176",
            "stage12370_full_selected_test_anti_collapse_ledger_v8:134",
            "stage12376_combined_train_support_ledger_v11:158",
            "stage12379_combined_train_support_ledger_v12:170",
            "stage12381_combined_train_support_ledger_v13:178",
        ],
        "active_policy_summary": {
            "org_caps_are_not_hard_blocks": True,
            "diversity_weighting_required": True,
            "MCP_core_train_support_reconsiderable": ((policy.get("weighted_warnings_not_hard_rejects") or {}).get("MCP_core") is not None),
            "Open_SWE_requires_safe_semantic_extraction": ((policy.get("weighted_warnings_not_hard_rejects") or {}).get("Open_SWE") is not None),
            "row_local_training_allowed_is_not_global_training_clearance": True,
        },
        "completed_corrections_since_stage12370": [
            "C++ task-specific re-render with C++ double-count fix",
            "Git Rust task-specific re-render",
            "Python Stage12326 task-specific re-render",
            "Web fallback/MCP task-specific re-render under diversity policy",
            "OpenClaw task-specific re-render with raw command removal",
            "Einops task-specific re-render",
        ],
        "remaining_named_blockers": ledger.get("training_blockers"),
        "next_recoverable_pools": [
            "Luxon Web root: re-render or defer because prior dependency-path visibility risk",
            "Open-SWE QC: safe semantic extraction only, no direct admission",
            "Fresh non-web Rust/C++ roots: preferred for balance after re-render cleanup",
        ],
    }
    (OUT / "current_dataset_control_board_v4.json").write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
