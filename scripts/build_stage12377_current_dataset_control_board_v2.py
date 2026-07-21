#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12377_current_dataset_control_board_v2"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
LEDGER = ROOT / "runs/summaries/stage12376_combined_train_support_ledger_v11.json"
POLICY = ROOT / "runs/summaries/stage12364_diversity_weighted_admission_policy.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ledger = read_json(LEDGER)
    policy = read_json(POLICY)
    control = {
        "stage": STAGE,
        "decision": "current_dataset_control_board_v2_ready",
        "training_allowed": False,
        "claim_boundary": "Control board only. No rows admitted.",
        "selected_current_ledger_ref": str(LEDGER),
        "selected_policy_ref": str(POLICY),
        "current_honest_train_support_tasks": ledger.get("current_admitted_train_support_tasks"),
        "remaining_gap_to_500": ledger.get("remaining_gap_to_500"),
        "language_counts": ledger.get("language_counts"),
        "task_family_counts": ledger.get("task_family_or_record_type_counts"),
        "stale_counts_not_authoritative": [
            "stage12363_combined_train_support_ledger_v6:176",
            "stage12370_full_selected_test_anti_collapse_ledger_v8:134",
            "stage12373_combined_train_support_ledger_v9:138",
            "stage12375_combined_train_support_ledger_v10:146",
        ],
        "active_policy_summary": {
            "org_caps_are_not_hard_blocks": True,
            "diversity_weighting_required": True,
            "MCP_core_train_support_reconsiderable": ((policy.get("weighted_warnings_not_hard_rejects") or {}).get("MCP_core") is not None),
            "Open_SWE_requires_safe_semantic_extraction": ((policy.get("weighted_warnings_not_hard_rejects") or {}).get("Open_SWE") is not None),
            "row_local_training_allowed_is_not_global_training_clearance": True,
        },
        "completed_corrections": [
            "Stage12364 replaced hard org cap with diversity-weighted policy.",
            "Stage12370 quarantined collapsed selected-test projections across older sources.",
            "Stage12375 removed C++/Git double-counting after task-specific re-renders.",
            "Stage12376 replaced Stage12326 Python collapsed roots with task-specific re-renders.",
        ],
        "next_recoverable_pools": [
            "stage12351_web_fallback_selected_test_admissions: 3 roots / 12 recoverable rows, medium risk",
            "stage12360_einops_selected_test: 1 root / 4 recoverable rows, low-medium risk",
            "stage12331/stage12339/stage12343 web roots: 3 roots / 12 recoverable rows, medium-high risk",
        ],
        "training_blockers": ledger.get("training_blockers"),
    }
    (OUT / "current_dataset_control_board_v2.json").write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(control, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
