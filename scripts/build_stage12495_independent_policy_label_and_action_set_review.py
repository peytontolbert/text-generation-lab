#!/usr/bin/env python3
"""Independent policy-label and candidate-action-set review worklist.

Stage12495 prepares review work items from Stage12494 packets. It separates
task-specific candidate grammar from gold-label adjudication so observed
actions cannot become targets by construction. It emits no training rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12495_independent_policy_label_and_action_set_review"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12494 = "stage12494_root_local_source_record_materializer"
PACKETS = ROOT / "runs/local/artifacts" / STAGE12494 / "root_local_materialization_review_packets.jsonl"
STAGE12494_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12494}.json"

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
    "independent_policy_labels_admitted": 0,
}

ACTION_GRAMMAR = {
    "transition_next_action": [
        "RETRIEVE_EVIDENCE",
        "SELECT_TEST",
        "INSPECT_SOURCE",
        "PLAN_PATCH",
        "RUN_VERIFIER",
        "FINISH",
        "ABSTAIN_OR_ESCALATE",
    ],
    "transition_verifier_transition": [
        "PASS_CURRENT_STATE",
        "PASS_CURRENT_BUILD",
        "PASS_CURRENT_BUILD_AND_RUN",
        "FAIL_CURRENT_STATE",
        "FAIL_TO_PASS",
        "NOT_EXERCISED",
        "INSUFFICIENT_EVIDENCE",
    ],
    "transition_continue_or_stop": [
        "CONTINUE_RETRIEVE",
        "CONTINUE_VERIFY",
        "CONTINUE_REPLAN",
        "STOP_DONE",
        "STOP_BLOCKED",
        "ABSTAIN_INSUFFICIENT_EVIDENCE",
    ],
    "event_local_transition_observation": [
        "PATCH_APPLIED_OBSERVED",
        "PATCH_FAILED_OBSERVED",
        "NO_PATCH_OBSERVED",
        "VERIFIER_PASS_OBSERVED",
        "VERIFIER_FAILURE_OBSERVED",
        "VERIFIER_ENV_BLOCKED_OBSERVED",
        "VERIFIER_TIMEOUT_OBSERVED",
    ],
}

ACCEPTANCE_CRITERIA = {
    "transition_next_action": [
        "gold_action_derived_from_state_not_observed_action",
        "must_include_patch_too_early_negative_when_relevant",
        "must_include_finish_too_early_negative_when_relevant",
    ],
    "transition_verifier_transition": [
        "gold_status_derived_from_verifier_observation_semantics",
        "must_distinguish_build_only_from_build_and_run",
        "must_include_insufficient_or_not_exercised_negative",
    ],
    "transition_continue_or_stop": [
        "gold_control_decision_derived_from_completion_gate",
        "must_include_stop_wrong_when_verifier_incomplete",
        "must_include_continue_wrong_when_done",
    ],
    "event_local_transition_observation": [
        "observation_status_only_no_policy_label",
        "must_not_promote_to_level3_or_next_action_policy",
        "must_keep_target_hidden_from_model_input",
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


def candidate_options(task_family: str) -> list[dict[str, Any]]:
    grammar = ACTION_GRAMMAR.get(task_family, ["TASK_SPECIFIC_REVIEW_REQUIRED"])
    labels = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    return [
        {
            "label": labels[index],
            "semantic_role_hash": stable_hash({"task_family": task_family, "role": role}),
            "target_visible": False,
            "is_gold": False,
        }
        for index, role in enumerate(grammar)
    ]


def review_item(packet: dict[str, Any]) -> dict[str, Any]:
    task_family = str(packet.get("task_family") or "unknown")
    source_kind = str(packet.get("source_record_kind") or "unknown")
    is_event_local = task_family == "event_local_transition_observation"
    blockers = [
        "independent_policy_label_missing",
        "policy_label_missing_independent_evidence_rationale",
        "reviewer_independence_attestation_missing",
        "candidate_option_rationale_missing",
        "candidate_action_set_missing_hard_negatives",
        "state_before_semantic_review_missing",
        "state_delta_semantic_review_missing",
        "anti_shortcut_audit_missing",
        "option_permutation_audit_missing",
        "deterministic_blinded_shuffle_missing",
    ]
    if "observed_action" in " ".join(packet.get("source_limitations", [])):
        blockers.append("observed_action_exposure_risk")
    if is_event_local:
        blockers.append("event_local_support_only_no_policy_target")
    if source_kind == "combined_train_support_source":
        blockers.append("selected_test_or_template_source_requires_extra_review")
    return {
        "record_type": "stage12495_independent_policy_label_review_work_item_v1",
        "review_item_id_hash": stable_hash({"packet": packet.get("packet_id_hash")}),
        "packet_id_hash": packet.get("packet_id_hash"),
        "source_candidate_id_hash": packet.get("source_candidate_id_hash"),
        "work_item_id_hash": packet.get("work_item_id_hash"),
        "language_family": packet.get("language_family"),
        "task_family": task_family,
        "source_record_kind": source_kind,
        "root_lineage_key_hash": packet.get("root_lineage_key_hash"),
        "source_family_hash": packet.get("source_family_hash"),
        "candidate_option_set_hash": stable_hash(candidate_options(task_family)),
        "candidate_option_count": len(candidate_options(task_family)),
        "candidate_options_public_safe": candidate_options(task_family),
        "gold_label_status": "missing_independent_review",
        "gold_label_hash": None,
        "reviewer_independence_attestation": False,
        "local_model_authority": False,
        "raw_private_values_revealed": False,
        "observed_action_available_to_labeler": False,
        "deterministic_blinded_shuffle": False,
        "acceptance_criteria": ACCEPTANCE_CRITERIA.get(task_family, ["task_family_acceptance_criteria_missing"]),
        "blocker_codes": sorted(set(blockers)),
        "observed_action_exposure_risk": any("observed_action" in item for item in packet.get("source_limitations", [])),
        "event_local_promoted": False,
        "claim_boundary": {
            "policy_label_review_work_item": True,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12494_summary = read_json(STAGE12494_SUMMARY)
    packets = read_jsonl(PACKETS)
    review_items = [review_item(packet) for packet in packets]

    language_counts = Counter(row["language_family"] for row in review_items)
    task_counts = Counter(row["task_family"] for row in review_items)
    source_kind_counts = Counter(row["source_record_kind"] for row in review_items)
    blocker_counts: Counter[str] = Counter()
    for row in review_items:
        blocker_counts.update(row["blocker_codes"])
    observed_action_exposure_count = sum(1 for row in review_items if row["observed_action_exposure_risk"])
    event_local_count = task_counts.get("event_local_transition_observation", 0)
    event_local_promoted_count = sum(1 for row in review_items if row["event_local_promoted"])

    issue_hashes = scan({"review_items": review_items})
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    summary = {
        "stage": STAGE,
        "record_type": "stage12495_independent_policy_label_and_action_set_review_summary_v1",
        "decision": "policy_label_review_worklist_ready_training_blocked"
        if review_items and guardrail["scan_passed"]
        else "blocked_empty_or_guardrail_failed",
        "source_stage_refs": [STAGE12494],
        "stage12494_review_packet_count": stage12494_summary.get("review_packet_count", len(packets)),
        "stage12494_blocked_packet_count": stage12494_summary.get("blocked_packet_count"),
        "stage12494_complete_review_packet_count": stage12494_summary.get("complete_review_packet_count"),
        "input_packet_count": len(packets),
        "review_item_count": len(review_items),
        "review_completed_count": 0,
        "accepted_policy_label_count": 0,
        "blocked_review_item_count": len(review_items),
        "observed_action_exposure_count": observed_action_exposure_count,
        "candidate_action_set_leak_count": 0,
        "event_local_input_count": event_local_count,
        "event_local_blocked_count": event_local_count,
        "event_local_promoted_count": event_local_promoted_count,
        "local_model_suggestions_authoritative_count": 0,
        "private_raw_value_output_count": 0,
        "observed_action_imitation_failure_count": 0,
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "source_record_kind_counts": dict(sorted(source_kind_counts.items())),
        "blocker_counts": dict(sorted(blocker_counts.items())),
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": "stage12496_policy_label_review_return_validator",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "items": len(review_items),
                "blockers": dict(blocker_counts),
                "tasks": dict(task_counts),
            }
        ),
    }

    write_jsonl(OUT / "independent_policy_label_review_work_items.jsonl", review_items)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
