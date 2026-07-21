#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12318_event_local_observation_package_qc"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12317_ROWS = (
    ROOT
    / "runs/local/artifacts/stage12317_event_local_observation_train_support_500"
    / "event_local_observation_train_support_tasks.jsonl"
)


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


def candidate_bucket(row: dict[str, Any]) -> str:
    target = row.get("target_view") or {}
    rule = target.get("semantic_rule_id") or "MISSING"
    verifier = target.get("verifier_status_class") or "MISSING"
    patch = target.get("patch_apply_status") or "MISSING"
    return f"{rule}::{patch}::{verifier}"


def review_status(row: dict[str, Any]) -> tuple[str, list[str]]:
    target = row.get("target_view") or {}
    blockers = []
    if not target.get("semantic_rule_id") or not target.get("transition_function_key"):
        blockers.append("missing_rule_or_transition_key")
    if target.get("verifier_status_class") in {"NO_VERIFIER_OBSERVED", "VERIFIER_STATUS_UNKNOWN", None}:
        blockers.append("missing_training_grade_verifier_status")
    if target.get("patch_apply_status") in {"PATCH_STATUS_UNKNOWN", None}:
        blockers.append("missing_training_grade_patch_status")
    blockers.extend(
        [
            "policy_label_not_reviewed",
            "repo_family_not_recovered",
            "state_delta_not_semantically_reviewed",
            "not_level3_repair_causality",
        ]
    )
    if len(blockers) == 4:
        return "semantic_review_candidate", blockers
    return "blocked_before_semantic_review", blockers


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rows = read_jsonl(STAGE12317_ROWS)
    review_rows = []
    status_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()
    bucket_counts: Counter[str] = Counter()
    chat_counts: Counter[str] = Counter()
    risky_fields: Counter[str] = Counter()
    unique_windows = set()
    for row in rows:
        status, blockers = review_status(row)
        status_counts[status] += 1
        blocker_counts.update(blockers)
        bucket_counts[candidate_bucket(row)] += 1
        task_window_id = (row.get("source_refs") or {}).get("task_window_id")
        if task_window_id:
            unique_windows.add(task_window_id)
        chat_hash = (row.get("source_refs") or {}).get("chat_id_hash") or "unknown"
        chat_counts[chat_hash] += 1
        for action in (((row.get("input_view") or {}).get("candidate_action_set") or {}).get("actions") or []):
            for key in action:
                if key in {"role", "chosen", "gold", "correct", "target", "observed", "observed_in_window", "count_bucket"} or key.endswith("_ref"):
                    risky_fields[key] += 1
        review_rows.append(
            {
                "stage": STAGE,
                "source_row_id": row.get("row_id"),
                "task_window_id": task_window_id,
                "review_status": status,
                "candidate_bucket": candidate_bucket(row),
                "review_required_before_training": True,
                "blocked_reasons": sorted(set(blockers)),
                "train_support_allowed_after_stage12318": False,
            }
        )
    write_jsonl(OUT / "event_local_observation_qc_records.jsonl", review_rows)

    semantic_review_candidates = status_counts["semantic_review_candidate"]
    summary = {
        "stage": STAGE,
        "decision": "event_local_500_candidate_package_qc_complete_training_blocked",
        "claim_boundary": "QC artifact only. Stage12317 produced 500 review candidates, not 500 admitted training tasks.",
        "training_allowed": False,
        "input_records": len(rows),
        "review_candidates": semantic_review_candidates,
        "admitted_training_tasks": 0,
        "level3_admitted": 0,
        "patch_trace_admitted": 0,
        "unique_task_windows": len(unique_windows),
        "status_counts": dict(status_counts),
        "blocked_reason_counts": dict(blocker_counts),
        "candidate_bucket_counts": dict(bucket_counts.most_common(20)),
        "dominance": {
            "unique_chat_hashes": len(chat_counts),
            "top_chat_count": chat_counts.most_common(1)[0][1] if chat_counts else 0,
            "top_chat_fraction": (chat_counts.most_common(1)[0][1] / max(1, len(rows))) if chat_counts else 0,
        },
        "risky_candidate_action_field_counts": dict(risky_fields),
        "realistic_admission_upper_bound": {
            "immediate_without_review": 0,
            "after_semantic_review": "not_more_than_review_candidates_and_likely_less_due_repo/state_delta_policy_checks",
            "minimum_next_target": "review 100 candidates into >=50 admitted event-local observation train-support tasks before scaling further",
        },
        "next_stage": {
            "stage": "stage12319_event_local_semantic_review_materializer",
            "purpose": "Review a capped, balanced subset of event-local candidates and admit only target-hidden observation/status tasks.",
            "training_allowed": False,
        },
    }
    (OUT / "event_local_observation_package_qc_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (OUT / "EVENT_LOCAL_OBSERVATION_PACKAGE_QC_STAGE12318.md").write_text(
        "# Stage12318 Event-Local Observation Package QC\n\n"
        "Stage12317 is correctly treated as a 500-record review candidate package, not as 500 admitted training tasks.\n\n"
        "The next step is semantic review/materialization into target-hidden observation/status tasks.\n",
        encoding="utf-8",
    )
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
