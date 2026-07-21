#!/usr/bin/env python3
"""Fail-closed root-local source record materializer.

Stage12494 converts Stage12493 source-adapter candidates into bounded review
packets. It does not emit training rows. A packet is complete only when it has
root-local state codes, rewritten action candidates, an independent policy
label, state-delta review, renderer contract, and anti-shortcut audit.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12494_root_local_source_record_materializer"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12493 = "stage12493_root_local_concept_source_adapter"
SOURCE_CANDIDATES = ROOT / "runs/local/artifacts" / STAGE12493 / "root_local_source_candidate_records.jsonl"
STAGE12493_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12493}.json"

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)

FALSE_GUARDS = {
    "training_allowed": False,
    "admission_allowed": False,
    "packaging_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
    "network_performed_by_stage": False,
}

ZERO_GUARDS = {
    "training_rows_emitted": 0,
    "admitted_rows": 0,
    "reviewed_train_support_rows": 0,
    "proof_grade_repair_rows": 0,
    "external_repair_credit_count": 0,
    "sealed_eval_rows": 0,
    "complete_root_local_materialized_rows": 0,
}

REQUIRED_COMPLETION_SLOTS = [
    "state_before_codes",
    "candidate_action_set_rewritten_hash",
    "independent_policy_label_hash",
    "observation_status_class",
    "state_delta_codes",
    "stop_continue_label_hash",
    "renderer_contract_hash",
    "anti_shortcut_audit_hash",
]

OBSERVATION_CLASS_BY_SOURCE_KIND = {
    "direct_authoritative_verifier_observation_source": "VERIFIER_OBSERVATION_AVAILABLE_REVIEW_REQUIRED",
    "controlled_triple_fail_to_pass_source": "CONTROLLED_FAIL_TO_PASS_OBSERVATION_REVIEW_REQUIRED",
    "direct_verifier_log_bounded_train_support_source": "BOUNDED_VERIFIER_LOG_OBSERVATION_REVIEW_REQUIRED",
    "combined_train_support_source": "COMBINED_SUPPORT_OBSERVATION_REVIEW_REQUIRED",
    "event_local_observation_status_source": "EVENT_LOCAL_STATUS_OBSERVATION_REVIEW_REQUIRED",
    "paired_action_observation_weak_policy_source": "PAIRED_ACTION_OBSERVATION_WEAK_REVIEW_REQUIRED",
    "embedding_diversity_priority_source": "EMBEDDING_PRIORITY_NO_OBSERVATION_REVIEW_REQUIRED",
}

STATE_CODES_BY_TASK = {
    "transition_next_action": [
        "TASK_FAMILY_NEXT_ACTION",
        "SOURCE_CANDIDATE_BOUND",
        "POLICY_LABEL_NOT_INDEPENDENT_YET",
    ],
    "transition_verifier_transition": [
        "TASK_FAMILY_VERIFIER_TRANSITION",
        "VERIFIER_OBSERVATION_REF_AVAILABLE",
        "STATUS_REVIEW_REQUIRED",
    ],
    "transition_continue_or_stop": [
        "TASK_FAMILY_CONTINUE_OR_STOP",
        "STOP_DECISION_REF_AVAILABLE",
        "COMPLETION_GATE_REVIEW_REQUIRED",
    ],
    "event_local_transition_observation": [
        "TASK_FAMILY_EVENT_LOCAL_OBSERVATION",
        "EVENT_LOCAL_SUPPORT_ONLY",
        "NOT_LEVEL3_REPAIR_PROOF",
    ],
}

TASK_ACTION_FAMILIES = {
    "transition_next_action": ["RETRIEVE_EVIDENCE", "SELECT_TEST", "PLAN_PATCH", "RUN_VERIFIER", "FINISH", "ABSTAIN"],
    "transition_verifier_transition": [
        "PASS_CURRENT_STATE",
        "PASS_CURRENT_BUILD",
        "PASS_CURRENT_BUILD_AND_RUN",
        "FAIL_CURRENT_STATE",
        "INSUFFICIENT_EVIDENCE",
        "NOT_EXERCISED",
    ],
    "transition_continue_or_stop": ["CONTINUE", "STOP_DONE", "RETRY", "REPLAN", "ESCALATE", "ABSTAIN"],
    "event_local_transition_observation": [
        "PATCH_APPLIED",
        "PATCH_FAILED",
        "NO_PATCH_OBSERVED",
        "VERIFIER_PASS_OBSERVED",
        "VERIFIER_FAILURE_OBSERVED",
        "VERIFIER_ENV_BLOCKED_OBSERVED",
    ],
}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def scan(value: Any) -> list[str]:
    issues: list[str] = []
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(stable_hash(value))
    elif isinstance(value, dict):
        for child in value.values():
            issues.extend(scan(child))
    elif isinstance(value, list):
        for child in value:
            issues.extend(scan(child))
    return issues


def unresolved_slots(row: dict[str, Any]) -> list[str]:
    missing = []
    # Stage12493 provides source hashes, but not root-local reviewed values.
    for slot in REQUIRED_COMPLETION_SLOTS:
        if slot == "observation_status_class":
            continue
        missing.append(slot)
    if row.get("source_record_kind") == "embedding_diversity_priority_source":
        missing.append("observation_status_class")
    return missing


def review_packet(row: dict[str, Any]) -> dict[str, Any]:
    task_family = str(row.get("task_family") or "unknown")
    source_kind = str(row.get("source_record_kind") or "unknown")
    missing = unresolved_slots(row)
    state_codes = STATE_CODES_BY_TASK.get(task_family, ["UNKNOWN_TASK_FAMILY_REVIEW_REQUIRED"])
    candidate_roles = TASK_ACTION_FAMILIES.get(task_family, ["TASK_SPECIFIC_CANDIDATES_REQUIRED"])
    return {
        "record_type": "stage12494_root_local_materialization_review_packet_v1",
        "packet_id_hash": stable_hash({"source_candidate": row.get("candidate_id_hash")}),
        "source_candidate_id_hash": row.get("candidate_id_hash"),
        "work_item_id_hash": row.get("work_item_id_hash"),
        "source_record_ref_hash": row.get("source_record_ref_hash"),
        "source_stage": row.get("source_stage"),
        "source_record_kind": source_kind,
        "language_family": row.get("language_family"),
        "task_family": task_family,
        "source_task_family": row.get("source_task_family"),
        "source_family_hash": row.get("source_family_hash"),
        "root_lineage_key_hash": row.get("root_lineage_key_hash"),
        "transition_function_key_hash": row.get("transition_function_key_hash"),
        "derived_state_before_codes": state_codes,
        "candidate_action_family_set_hash": stable_hash(candidate_roles),
        "candidate_action_family_count": len(candidate_roles),
        "observation_status_class_candidate": OBSERVATION_CLASS_BY_SOURCE_KIND.get(
            source_kind, "UNKNOWN_OBSERVATION_REVIEW_REQUIRED"
        ),
        "state_delta_candidate_codes": [
            "STATE_DELTA_NOT_REVIEWED",
            "NO_REPAIR_CLAIM",
            "NO_SEALED_EVAL_CLAIM",
        ],
        "stop_continue_candidate_hash": stable_hash({"task_family": task_family, "source": row.get("observation_ref_hash")}),
        "completion_slots_required": REQUIRED_COMPLETION_SLOTS,
        "completion_slots_missing": missing,
        "materialization_status": "blocked_pending_independent_review",
        "blocker_codes": sorted(
            set(
                [
                    "candidate_action_set_must_be_rewritten_without_observed_action_markers",
                    "independent_policy_label_missing",
                    "renderer_contract_missing",
                    "anti_shortcut_audit_missing",
                    "state_delta_review_missing",
                    "root_local_source_reopen_or_trace_join_required",
                ]
                + (
                    ["event_local_support_cannot_promote_to_level3"]
                    if task_family == "event_local_transition_observation"
                    else []
                )
                + (
                    ["controlled_fixture_not_external_repair_credit"]
                    if source_kind == "controlled_triple_fail_to_pass_source"
                    else []
                )
            )
        ),
        "source_limitations": row.get("source_limitations", []),
        "claim_boundary": {
            "materialization_review_packet": True,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12493_summary = read_json(STAGE12493_SUMMARY)
    source_candidates = read_jsonl(SOURCE_CANDIDATES)
    packets = [review_packet(row) for row in source_candidates]
    blocked = [
        {
            "record_type": "stage12494_blocked_materialization_ref_v1",
            "packet_id_hash": row["packet_id_hash"],
            "source_candidate_id_hash": row["source_candidate_id_hash"],
            "task_family": row["task_family"],
            "language_family": row["language_family"],
            "blocker_codes": row["blocker_codes"],
            "completion_slots_missing": row["completion_slots_missing"],
            **FALSE_GUARDS,
            **ZERO_GUARDS,
        }
        for row in packets
    ]

    language_counts = Counter(row["language_family"] for row in packets)
    task_counts = Counter(row["task_family"] for row in packets)
    source_kind_counts = Counter(row["source_record_kind"] for row in packets)
    source_family_counts = Counter(row["source_family_hash"] for row in packets)
    missing_counts: Counter[str] = Counter()
    for row in packets:
        missing_counts.update(row["completion_slots_missing"])
    max_source_family_share = max(source_family_counts.values()) / len(packets) if packets else 0.0

    issue_hashes = scan({"packets": packets, "blocked": blocked})
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    complete_count = sum(1 for row in packets if not row["completion_slots_missing"])
    summary = {
        "stage": STAGE,
        "record_type": "stage12494_root_local_source_record_materializer_summary_v1",
        "decision": "materialization_review_packets_ready_training_blocked"
        if packets and guardrail["scan_passed"]
        else "blocked_empty_or_guardrail_failed",
        "source_stage_refs": [STAGE12493],
        "stage12493_source_candidate_count": stage12493_summary.get("source_candidate_count", len(source_candidates)),
        "review_packet_count": len(packets),
        "blocked_packet_count": len(blocked),
        "complete_review_packet_count": complete_count,
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_record_kind_counts": dict(sorted(source_kind_counts.items())),
        "completion_slot_missing_counts": dict(sorted(missing_counts.items())),
        "max_source_family_share": round(max_source_family_share, 4),
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": "stage12495_independent_policy_label_and_action_set_review",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "packets": len(packets),
                "missing": dict(missing_counts),
                "languages": dict(language_counts),
            }
        ),
    }

    write_jsonl(OUT / "root_local_materialization_review_packets.jsonl", packets)
    write_jsonl(OUT / "blocked_materialization_refs.jsonl", blocked)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
