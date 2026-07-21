#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12298_transition_training_package_candidate"
STAGE12295_ROWS = ROOT / "runs/local/artifacts/stage12295_transition_function_ledger/transition_function_train_support_rows.jsonl"
STAGE12297_ROWS = ROOT / "runs/local/artifacts/stage12297_horizon_source_root_repair_and_projection_admission/admitted_horizon_transition_train_support_rows.jsonl"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

V1_TARGET_CAP = 120
ALLOWED_V1_ACTIONS = {
    "READ_OR_SEARCH",
    "RUN_OR_VERIFY",
    "EDIT_PATCH",
    "VERSION_CONTROL",
    "ENVIRONMENT_SETUP",
}


def iter_jsonl(path: Path):
    if not path.exists():
        return
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                yield json.loads(line)


def write_jsonl(path: Path, rows: list[dict]) -> int:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")
    return len(rows)


def as_package_row(row: dict, source_tier: str, source_stage: str) -> dict:
    out = dict(row)
    out["package_stage"] = STAGE
    out["source_tier"] = source_tier
    out["source_stage"] = source_stage
    out["package_admission"] = {
        "candidate_package_only": True,
        "training_allowed": False,
        "requires_projection_qc": True,
        "strict_eval_eligible": False,
        "external_comparable_patch_trace_countable": False,
        "external_fail_to_pass_countable": False,
    }
    return out


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    high_quality = [
        as_package_row(row, "tier_a_horizon_root_repaired_v3", "stage12297")
        for row in (iter_jsonl(STAGE12297_ROWS) or [])
    ]

    selected_v1 = []
    blocked_v1 = []
    action_counts: Counter[str] = Counter()
    for row in iter_jsonl(STAGE12295_ROWS) or []:
        if row.get("validation_level") != "V1_PAIRED_ACTION_OBSERVATION":
            continue
        action = row.get("target_semantic_action")
        if action not in ALLOWED_V1_ACTIONS:
            blocked_v1.append({"row_id": row.get("row_id"), "blocked_reason": "v1_action_family_too_broad_or_control_plane", "target_semantic_action": action})
            continue
        if action_counts[action] >= V1_TARGET_CAP:
            blocked_v1.append({"row_id": row.get("row_id"), "blocked_reason": "v1_action_family_cap_reached", "target_semantic_action": action})
            continue
        selected_v1.append(as_package_row(row, "tier_b_balanced_v1_action_observation", "stage12295"))
        action_counts[action] += 1

    package_rows = high_quality + selected_v1
    write_jsonl(OUT / "transition_training_package_candidate_rows.jsonl", package_rows)
    write_jsonl(OUT / "blocked_v1_transition_rows.jsonl", blocked_v1)

    summary = {
        "stage": STAGE,
        "decision": "transition_training_package_candidate_ready_for_qc_no_training",
        "claim_boundary": "Candidate train-support package only. No training request emitted.",
        "package_rows": len(package_rows),
        "tier_counts": dict(Counter(row["source_tier"] for row in package_rows)),
        "task_family_counts": dict(Counter(row.get("task_family") for row in package_rows)),
        "target_semantic_action_counts": dict(Counter(row.get("target_semantic_action") for row in package_rows if row.get("target_semantic_action")).most_common()),
        "language_counts": dict(Counter(row.get("language_family", "unknown") for row in package_rows)),
        "blocked_v1_rows": len(blocked_v1),
        "blocked_v1_reason_counts": dict(Counter(row["blocked_reason"] for row in blocked_v1)),
        "proof_counts": {
            "strict_eval_eligible": 0,
            "source_heldout_admissible": 0,
            "external_comparable_patch_trace_countable": 0,
            "external_fail_to_pass_countable": 0,
        },
        "quality_notes": [
            "tier_a rows are source-root repaired horizon rows from Stage12297",
            "tier_b rows are balanced V1 action-observation support only",
            "CONTROL_PLANE and OTHER_ACTION V1 rows are excluded",
            "V3 child-loop verifier/continue rows remain excluded until semantic/causal review",
        ],
        "next_stage": "stage12299_transition_training_package_qc",
        "training_allowed": False,
        "raw_output_emitted": False,
    }
    (OUT / "transition_training_package_candidate_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "TRANSITION_TRAINING_PACKAGE_CANDIDATE_STAGE12298.md").write_text(
        "# Stage12298 Transition Training Package Candidate\n\n"
        + "Candidate package only; no training request emitted.\n\n"
        + "```json\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n```\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
