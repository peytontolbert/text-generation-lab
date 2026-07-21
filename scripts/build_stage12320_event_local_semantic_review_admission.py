#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12320_event_local_semantic_review_admission"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12317_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12317_event_local_observation_train_support_500"
    / "event_local_observation_train_support_tasks.jsonl"
)
STAGE12318_QC = (
    ROOT
    / "runs/local/artifacts/stage12318_event_local_observation_package_qc"
    / "event_local_observation_qc_records.jsonl"
)

TARGET_ADMISSIONS = 100
MAX_PER_CHAT = 3
MAX_PER_SOURCE_HASH = 3
BUCKET_QUOTAS = {
    "RULE_PATCH_APPLIED_THEN_VERIFIER_PASS::PATCH_APPLIED::VERIFIER_PASS_OBSERVED": 18,
    "RULE_PATCH_APPLIED_THEN_VERIFIER_FAIL::PATCH_APPLIED::VERIFIER_FAILURE_OBSERVED": 18,
    "RULE_PATCH_APPLICATION_FAILED::PATCH_FAILED::VERIFIER_FAILURE_OBSERVED": 12,
    "RULE_PATCH_APPLICATION_FAILED::PATCH_FAILED::VERIFIER_PASS_OBSERVED": 14,
    "RULE_NO_PATCH_VERIFIER_OBSERVATION::NO_PATCH_OBSERVED::VERIFIER_PASS_OBSERVED": 18,
    "RULE_NO_PATCH_VERIFIER_OBSERVATION::NO_PATCH_OBSERVED::VERIFIER_FAILURE_OBSERVED": 10,
    "RULE_NO_PATCH_VERIFIER_OBSERVATION::NO_PATCH_OBSERVED::VERIFIER_ENV_BLOCKED_OBSERVED": 3,
    "RULE_NO_PATCH_VERIFIER_OBSERVATION::NO_PATCH_OBSERVED::VERIFIER_TIMEOUT_OBSERVED": 4,
    "RULE_PATCH_APPLICATION_FAILED::PATCH_FAILED::VERIFIER_ENV_BLOCKED_OBSERVED": 1,
    "RULE_PATCH_APPLICATION_FAILED::PATCH_FAILED::VERIFIER_TIMEOUT_OBSERVED": 2,
}

ALLOWED_RULES = {
    "RULE_PATCH_APPLIED_THEN_VERIFIER_PASS",
    "RULE_PATCH_APPLIED_THEN_VERIFIER_FAIL",
    "RULE_PATCH_APPLICATION_FAILED",
    "RULE_NO_PATCH_VERIFIER_OBSERVATION",
}
ALLOWED_VERIFIER_STATUS = {
    "VERIFIER_PASS_OBSERVED",
    "VERIFIER_FAILURE_OBSERVED",
    "VERIFIER_ENV_BLOCKED_OBSERVED",
    "VERIFIER_TIMEOUT_OBSERVED",
}
ALLOWED_PATCH_STATUS = {
    "PATCH_APPLIED",
    "PATCH_FAILED",
    "NO_PATCH_OBSERVED",
}
RISKY_ACTION_KEYS = {
    "role",
    "position_role",
    "action_ref",
    "tool_pair_ref",
    "chosen",
    "gold",
    "correct",
    "target",
    "observed",
    "observed_in_window",
    "count_bucket",
    "label",
    "is_correct",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def bucket(row: dict[str, Any]) -> str:
    target = row.get("target_view") or {}
    return "::".join(
        [
            target.get("semantic_rule_id") or "MISSING",
            target.get("patch_apply_status") or "MISSING",
            target.get("verifier_status_class") or "MISSING",
        ]
    )


def has_risky_candidate_fields(row: dict[str, Any]) -> list[str]:
    found = []
    for action in (((row.get("input_view") or {}).get("candidate_action_set") or {}).get("actions") or []):
        for key in action:
            if key in RISKY_ACTION_KEYS or key.endswith("_ref"):
                found.append(key)
    return sorted(set(found))


def admission_blockers(row: dict[str, Any], qc_status: str | None) -> list[str]:
    target = row.get("target_view") or {}
    blockers = []
    if qc_status != "semantic_review_candidate":
        blockers.append("not_stage12318_semantic_review_candidate")
    if target.get("semantic_rule_id") not in ALLOWED_RULES:
        blockers.append("semantic_rule_not_allowed")
    if not target.get("transition_function_key"):
        blockers.append("transition_function_key_missing")
    if target.get("verifier_status_class") not in ALLOWED_VERIFIER_STATUS:
        blockers.append("verifier_status_not_allowed")
    if target.get("patch_apply_status") not in ALLOWED_PATCH_STATUS:
        blockers.append("patch_status_not_allowed")
    risky = has_risky_candidate_fields(row)
    if risky:
        blockers.append("risky_candidate_action_fields:" + ",".join(risky))
    refs = row.get("source_refs") or {}
    if any(refs.get(flag) for flag in ["raw_text_emitted", "raw_command_text_emitted", "raw_tool_output_emitted", "raw_patch_body_emitted"]):
        blockers.append("raw_leak_guardrail_violation")
    return blockers


def make_train_row(row: dict[str, Any], source_rank: int) -> dict[str, Any]:
    target = row.get("target_view") or {}
    input_view = row.get("input_view") or {}
    candidate_set = input_view.get("candidate_action_set") or {}
    # Deliberately exclude observed_action_family_counts_audit_only from model input.
    model_input = {
        "state_before_summary_codes": input_view.get("state_before_summary_codes") or [],
        "candidate_action_set": candidate_set,
        "task_instruction": "Predict event-local observation/status classes from sanitized transition context. Do not infer next-action policy or repair success.",
    }
    return {
        "stage": STAGE,
        "record_type": "target_hidden_event_local_observation_status_train_support",
        "row_id": f"stage12320::{row.get('row_id')}",
        "source_row_id": row.get("row_id"),
        "task_family": "event_local_transition_observation",
        "split": "train_support_dev",
        "source_refs": row.get("source_refs") or {},
        "model_input_view": model_input,
        "target_only": {
            "patch_apply_status": target.get("patch_apply_status"),
            "verifier_status_class": target.get("verifier_status_class"),
            "state_delta_codes": target.get("state_delta_codes") or [],
            "stop_continue_label": target.get("stop_continue_label"),
            "semantic_rule_id": target.get("semantic_rule_id"),
            "transition_function_key": target.get("transition_function_key"),
        },
        "objective_scope": [
            "patch_apply_status_prediction",
            "verifier_status_class_prediction",
            "state_delta_code_prediction",
            "stop_continue_observation_prediction",
            "semantic_rule_classification",
        ],
        "not_objective_scope": [
            "transition_next_action_policy",
            "patch_generation",
            "Level3 repair causality",
            "strict_eval_or_source_heldout_claim",
        ],
        "admission": {
            "train_support_allowed": True,
            "training_allowed": True,
            "training_scope": "target_hidden_observation_status_only",
            "next_action_policy_allowed": False,
            "patch_generation_allowed": False,
            "repair_claim_admitted": False,
            "strict_eval_eligible": False,
            "source_heldout_admissible": False,
            "level3_admitted": False,
            "patch_trace_admitted": False,
        },
        "visibility_masks": {
            "model_input": ["model_input_view"],
            "target_only": ["target_only"],
            "never_emit_to_model": [
                "target_only",
                "observed_action_family_counts_audit_only",
                "raw_tool_output",
                "raw_tool_arguments",
                "raw_patch_body",
                "raw_source_path",
                "full_command_text",
            ],
        },
        "dominance_controls": {
            "selection_rank": source_rank,
            "max_per_chat": MAX_PER_CHAT,
            "max_per_source_hash": MAX_PER_SOURCE_HASH,
            "bucket_quotas": BUCKET_QUOTAS,
        },
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(STAGE12317_ROWS)
    qc_by_source = {
        row.get("source_row_id"): row
        for row in read_jsonl(STAGE12318_QC)
    }

    eligible = []
    blocked = []
    for row in rows:
        qc = qc_by_source.get(row.get("row_id")) or {}
        blockers = admission_blockers(row, qc.get("review_status"))
        item = {
            "source_row_id": row.get("row_id"),
            "task_window_id": (row.get("source_refs") or {}).get("task_window_id"),
            "chat_id_hash": (row.get("source_refs") or {}).get("chat_id_hash"),
            "candidate_bucket": bucket(row),
            "blockers": blockers,
        }
        if blockers:
            blocked.append(item)
        else:
            eligible.append((row, item))

    eligible.sort(key=lambda pair: (pair[1]["candidate_bucket"], pair[1]["chat_id_hash"] or "", pair[1]["task_window_id"] or ""))
    selected = []
    per_chat: Counter[str] = Counter()
    per_source_hash: Counter[str] = Counter()
    per_bucket: Counter[str] = Counter()
    seen_windows = set()
    # Fill explicit quotas bucket-by-bucket so common no-patch observations do not dominate.
    for quota_bucket, quota in BUCKET_QUOTAS.items():
        for row, item in eligible:
            cand_bucket = item["candidate_bucket"]
            if cand_bucket != quota_bucket:
                continue
            refs = row.get("source_refs") or {}
            chat = item["chat_id_hash"] or "unknown_chat"
            source_hash = refs.get("source_file_hash_compat") or "unknown_source_hash"
            task_window_id = item["task_window_id"]
            if task_window_id in seen_windows:
                continue
            if per_chat[chat] >= MAX_PER_CHAT:
                continue
            if per_source_hash[source_hash] >= MAX_PER_SOURCE_HASH:
                continue
            if per_bucket[cand_bucket] >= quota:
                continue
            selected.append(row)
            seen_windows.add(task_window_id)
            per_chat[chat] += 1
            per_source_hash[source_hash] += 1
            per_bucket[cand_bucket] += 1
            if len(selected) >= TARGET_ADMISSIONS:
                break
        if len(selected) >= TARGET_ADMISSIONS:
            break

    train_rows = [make_train_row(row, idx + 1) for idx, row in enumerate(selected)]
    write_jsonl(OUT / "event_local_observation_train_support_admitted_rows.jsonl", train_rows)
    write_jsonl(OUT / "event_local_observation_admission_blocked_rows.jsonl", blocked)

    target_counts: Counter[str] = Counter()
    verifier_counts: Counter[str] = Counter()
    patch_counts: Counter[str] = Counter()
    risky_fields: Counter[str] = Counter()
    for train_row in train_rows:
        target = train_row.get("target_only") or {}
        target_counts[target.get("semantic_rule_id") or "MISSING"] += 1
        verifier_counts[target.get("verifier_status_class") or "MISSING"] += 1
        patch_counts[target.get("patch_apply_status") or "MISSING"] += 1
        for action in (((train_row.get("model_input_view") or {}).get("candidate_action_set") or {}).get("actions") or []):
            for key in action:
                if key in RISKY_ACTION_KEYS or key.endswith("_ref"):
                    risky_fields[key] += 1

    blocked_counts: Counter[str] = Counter()
    for item in blocked:
        blocked_counts.update(item["blockers"])

    summary = {
        "stage": STAGE,
        "decision": "event_local_observation_train_support_admission_complete",
        "claim_boundary": "Narrow train-support rows only for event-local observation/status objectives. No next-action policy, no Level-3 repair, no strict/source-heldout claim.",
        "training_allowed": bool(train_rows),
        "input_candidates": len(rows),
        "eligible_after_semantic_review": len(eligible),
        "admitted_train_support_rows": len(train_rows),
        "target_admissions": TARGET_ADMISSIONS,
        "blocked_rows": len(blocked),
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "strict_eval_rows": 0,
        "source_heldout_rows": 0,
        "semantic_rule_counts": dict(target_counts),
        "verifier_status_counts": dict(verifier_counts),
        "patch_apply_status_counts": dict(patch_counts),
        "per_bucket_selected": dict(per_bucket),
        "per_chat_selected_top": dict(per_chat.most_common(20)),
        "per_source_hash_selected_top": dict(per_source_hash.most_common(20)),
        "bucket_quotas": BUCKET_QUOTAS,
        "blocked_reason_counts": dict(blocked_counts),
        "risky_model_input_candidate_action_field_counts": dict(risky_fields),
        "next_stage": {
            "stage": "stage12321_remaining_v4_event_local_candidate_materializer",
            "purpose": "Add remaining high-quality V4 review candidates, then rerun semantic admission.",
            "training_allowed": False,
        },
    }
    (OUT / "event_local_observation_train_support_admission_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "EVENT_LOCAL_SEMANTIC_REVIEW_ADMISSION_STAGE12320.md").write_text(
        "# Stage12320 Event-Local Semantic Review Admission\n\n"
        "This stage admits only narrow observation/status train-support rows. It intentionally does not admit next-action policy, Level-3 repair, strict eval, or source-heldout rows.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
