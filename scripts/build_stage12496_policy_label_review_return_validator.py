#!/usr/bin/env python3
"""Validate independent policy-label review returns.

Stage12496 validates review returns for Stage12495 work items. It is intentionally
fail-closed: no return file means zero accepted labels and zero trainable rows.
Even accepted labels remain review results only; renderer/state-delta/source
reopen gates are still required before training packaging.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12496_policy_label_review_return_validator"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12495 = "stage12495_independent_policy_label_and_action_set_review"
WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12495 / "independent_policy_label_review_work_items.jsonl"
STAGE12495_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12495}.json"
RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12495 / "independent_policy_label_review_returns.jsonl"

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
}

REQUIRED_RETURN_FIELDS = [
    "record_type",
    "review_item_id_hash",
    "packet_id_hash",
    "source_candidate_id_hash",
    "work_item_id_hash",
    "task_family",
    "language_family",
    "reviewer_id_hash",
    "reviewer_independence_attestation",
    "reviewer_conflict_check_hash",
    "candidate_option_set_hash",
    "candidate_action_set_rewritten_hash",
    "candidate_action_set_rewrite_rationale_hash",
    "independent_policy_label_hash",
    "independent_policy_label_rationale_hash",
    "state_before_semantic_review_hash",
    "state_delta_semantic_review_hash",
    "hard_negative_audit_hash",
    "anti_shortcut_audit_hash",
    "option_permutation_audit_hash",
    "deterministic_blinded_shuffle_hash",
    "observed_action_available_to_labeler",
    "observed_action_used_as_label",
    "local_model_authority",
    "raw_private_values_revealed",
    "event_local_promoted",
    "acceptance_criteria_passed",
    "blocker_codes",
    "training_allowed",
    "admission_allowed",
    "admitted_rows",
    "training_rows_emitted",
    "candidate_action_family_count",
    "hard_negative_count",
]

OUT_OF_SCOPE_BLOCKERS = [
    "renderer_contract_missing",
    "root_local_source_reopen_or_trace_join_required",
    "state_delta_review_missing",
]


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


def validate_return(row: dict[str, Any], work_item: dict[str, Any] | None) -> list[str]:
    reasons: list[str] = []
    if not row.get("review_item_id_hash"):
        reasons.append("missing_review_item_id_hash")
    if work_item is None:
        reasons.append("unknown_review_item_id_hash")
        return sorted(set(reasons))
    for field in REQUIRED_RETURN_FIELDS:
        if field not in row:
            reasons.append(f"missing_{field}")
    if row.get("record_type") != "stage12496_policy_label_review_return_v1":
        reasons.append("schema_version_unsupported")
    for field in ["packet_id_hash", "source_candidate_id_hash", "work_item_id_hash", "task_family", "language_family"]:
        if row.get(field) != work_item.get(field):
            reasons.append(f"{field}_mismatch")
    if row.get("candidate_option_set_hash") != work_item.get("candidate_option_set_hash"):
        reasons.append("candidate_option_set_hash_mismatch")
    if work_item.get("task_family") == "event_local_transition_observation":
        reasons.append("event_local_policy_label_attempted")
    if row.get("event_local_promoted") is not False:
        reasons.append("event_local_promoted")
    if row.get("reviewer_independence_attestation") is not True:
        reasons.append("reviewer_independence_attestation_missing")
    if not row.get("reviewer_conflict_check_hash"):
        reasons.append("reviewer_conflict_check_missing")
    if row.get("local_model_authority") is not False:
        reasons.append("local_model_authority_claimed")
    if row.get("raw_private_values_revealed") is not False:
        reasons.append("raw_private_value_revealed")
    if row.get("observed_action_available_to_labeler") is not False:
        reasons.append("observed_action_available_to_labeler")
    if row.get("observed_action_used_as_label") is not False:
        reasons.append("observed_action_used_as_label")
    if row.get("acceptance_criteria_passed") is not True:
        reasons.append("acceptance_criteria_failed")
    if row.get("training_allowed") is not False or row.get("admission_allowed") is not False:
        reasons.append("training_or_admission_requested")
    if row.get("training_rows_emitted") != 0:
        reasons.append("nonzero_training_rows_requested")
    if row.get("admitted_rows") != 0:
        reasons.append("nonzero_admitted_rows_requested")
    if not row.get("deterministic_blinded_shuffle_hash"):
        reasons.append("deterministic_blinded_shuffle_missing")
    if not row.get("option_permutation_audit_hash"):
        reasons.append("option_permutation_audit_missing")
    if int(row.get("candidate_action_family_count") or 0) < 6:
        reasons.append("candidate_action_family_count_below_6")
    if int(row.get("hard_negative_count") or 0) < 2:
        reasons.append("hard_negative_insufficient")
    if not row.get("hard_negative_audit_hash"):
        reasons.append("hard_negative_audit_missing")
    if row.get("candidate_action_set_rewritten_hash") == work_item.get("candidate_option_set_hash"):
        reasons.append("candidate_action_set_rewritten_hash_equals_original_when_rewrite_required")
    if not row.get("candidate_action_set_rewritten_hash"):
        reasons.append("candidate_action_set_rewritten_hash_missing")
    if not row.get("candidate_action_set_rewrite_rationale_hash"):
        reasons.append("candidate_action_set_rewrite_rationale_missing")
    if not row.get("independent_policy_label_hash"):
        reasons.append("independent_policy_label_hash_missing")
    if not row.get("independent_policy_label_rationale_hash"):
        reasons.append("policy_label_missing_independent_evidence_rationale")
    if not row.get("anti_shortcut_audit_hash"):
        reasons.append("anti_shortcut_audit_missing")
    if not row.get("state_before_semantic_review_hash"):
        reasons.append("state_before_semantic_review_missing")
    if not row.get("state_delta_semantic_review_hash"):
        reasons.append("state_delta_semantic_review_missing")
    if row.get("blocker_codes") not in ([], None):
        reasons.append("return_blocker_codes_not_empty")
    return sorted(set(reasons))


def accepted_record(row: dict[str, Any], work_item: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12496_validated_policy_label_review_result_v1",
        "validated_result_id_hash": stable_hash({"review": row.get("review_item_id_hash")}),
        "review_item_id_hash": row.get("review_item_id_hash"),
        "packet_id_hash": work_item.get("packet_id_hash"),
        "source_candidate_id_hash": work_item.get("source_candidate_id_hash"),
        "language_family": work_item.get("language_family"),
        "task_family": work_item.get("task_family"),
        "candidate_action_set_rewritten_hash": row.get("candidate_action_set_rewritten_hash"),
        "independent_policy_label_hash": row.get("independent_policy_label_hash"),
        "candidate_option_rationale_hash": row.get("candidate_option_rationale_hash"),
        "anti_shortcut_audit_hash": row.get("anti_shortcut_audit_hash"),
        "option_permutation_audit_hash": row.get("option_permutation_audit_hash"),
        "remaining_blocker_codes": OUT_OF_SCOPE_BLOCKERS,
        "claim_boundary": {
            "validated_policy_label_review": True,
            "reviewed_train_support": False,
            "level3_closed_loop_episode": False,
            "proof_grade_repair": False,
        },
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "independent_policy_labels_validated": 1,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    stage12495_summary = read_json(STAGE12495_SUMMARY)
    work_items = read_jsonl(WORK_ITEMS)
    returns = read_jsonl(RETURN_FILE)
    work_by_id = {row.get("review_item_id_hash"): row for row in work_items}

    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    return_id_counts = Counter(row.get("review_item_id_hash") for row in returns)
    duplicate_review_return_count = sum(count - 1 for count in return_id_counts.values() if count > 1)
    for row in returns:
        work_item = work_by_id.get(row.get("review_item_id_hash"))
        reasons = validate_return(row, work_item)
        if return_id_counts[row.get("review_item_id_hash")] > 1:
            reasons.append("duplicate_review_return")
        if reasons:
            reason_counts.update(reasons)
            rejected.append(
                {
                    "record_type": "stage12496_rejected_policy_label_review_return_v1",
                    "return_ref_hash": stable_hash(row),
                    "review_item_id_hash": row.get("review_item_id_hash"),
                    "reason_codes": reasons,
                    **FALSE_GUARDS,
                    **ZERO_GUARDS,
                    "independent_policy_labels_validated": 0,
                }
            )
        else:
            accepted.append(accepted_record(row, work_item))

    if not RETURN_FILE.exists():
        reason_counts.update({"return_file_missing": len(work_items)})

    language_counts = Counter(row["language_family"] for row in accepted)
    task_counts = Counter(row["task_family"] for row in accepted)
    issue_hashes = scan({"accepted": accepted, "rejected": rejected, "returns": returns})
    guardrail = {
        "stage": STAGE,
        "scan_passed": not issue_hashes,
        "raw_leak_count": len(issue_hashes),
        "issue_hashes": issue_hashes[:80],
    }
    decision = (
        "validated_policy_label_reviews_ready_still_training_blocked"
        if accepted and not rejected and guardrail["scan_passed"]
        else "blocked_policy_label_review_returns_missing_or_invalid"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12496_policy_label_review_return_validator_summary_v1",
        "decision": decision,
        "source_stage_refs": [STAGE12495],
        "expected_return_file": str(RETURN_FILE.relative_to(ROOT)),
        "return_file_present": RETURN_FILE.exists(),
        "stage12495_review_item_count": stage12495_summary.get("review_item_count", len(work_items)),
        "input_work_item_count": len(work_items),
        "review_return_count": len(returns),
        "input_return_count": len(returns),
        "valid_review_return_count": len(accepted),
        "invalid_review_return_count": len(rejected),
        "accepted_return_count": len(accepted),
        "rejected_return_count": len(rejected),
        "duplicate_review_return_count": duplicate_review_return_count,
        "missing_return_count": max(0, len(work_items) - len(returns)),
        "accepted_policy_label_count": len(accepted),
        "candidate_action_set_rewritten_count": len(accepted),
        "candidate_action_set_rewrite_rejected_count": len(rejected),
        "independent_policy_label_hash_valid_count": len(accepted),
        "independent_policy_labels_validated": len(accepted),
        "language_counts": dict(sorted(language_counts.items())),
        "task_family_counts": dict(sorted(task_counts.items())),
        "rejection_reason_counts": dict(sorted(reason_counts.items())),
        "reviewer_independence_pass_count": sum(1 for row in returns if row.get("reviewer_independence_attestation") is True),
        "reviewer_independence_fail_count": sum(1 for row in returns if row.get("reviewer_independence_attestation") is not True),
        "local_model_suggestions_authoritative_count": sum(1 for row in returns if row.get("local_model_authority") is not False),
        "local_model_authority_violation_count": sum(1 for row in returns if row.get("local_model_authority") is not False),
        "private_raw_value_output_count": sum(1 for row in returns if row.get("raw_private_values_revealed") is not False),
        "observed_action_leak_count": sum(1 for row in returns if row.get("observed_action_available_to_labeler") is not False),
        "observed_action_imitation_failure_count": sum(
            1 for row in returns if row.get("observed_action_available_to_labeler") is not False or row.get("observed_action_used_as_label") is not False
        ),
        "blinded_shuffle_pass_count": sum(1 for row in returns if row.get("deterministic_blinded_shuffle_hash")),
        "blinded_shuffle_fail_count": sum(1 for row in returns if not row.get("deterministic_blinded_shuffle_hash")),
        "hard_negative_pass_count": sum(1 for row in returns if int(row.get("hard_negative_count") or 0) >= 2),
        "hard_negative_fail_count": sum(1 for row in returns if int(row.get("hard_negative_count") or 0) < 2),
        "event_local_input_count": sum(1 for row in work_items if row.get("task_family") == "event_local_transition_observation"),
        "event_local_accepted_count": sum(1 for row in accepted if row.get("task_family") == "event_local_transition_observation"),
        "event_local_promoted_count": sum(1 for row in returns if row.get("event_local_promoted") is not False),
        "raw_leak_count": guardrail["raw_leak_count"],
        "next_stage": "stage12497_renderer_state_delta_source_reopen_gate",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "summary_hash": stable_hash(
            {
                "accepted": len(accepted),
                "rejected": len(rejected),
                "reasons": dict(reason_counts),
            }
        ),
    }

    write_jsonl(OUT / "validated_policy_label_review_results.jsonl", accepted)
    write_jsonl(OUT / "rejected_policy_label_review_returns.jsonl", rejected)
    write_json(OUT / "guardrail_scan.json", guardrail)
    write_json(OUT / "summary.json", summary)
    write_json(SUMMARY, summary)


if __name__ == "__main__":
    main()
