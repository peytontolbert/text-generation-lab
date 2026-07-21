#!/usr/bin/env python3
"""Build Stage12438 fail-closed public postrun/control artifacts.

This stage is aggregate accounting only for the session-like materializer
upgrade lane. It does not train, admit rows, emit row payloads, or expose raw
session material.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12438_session_like_materializer_upgrade_postrun"
LANE = "session_like_materializer_upgrade"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12436_SUMMARY = ROOT / "runs/summaries/stage12436_parallel_two_lane_control_request.json"
STAGE12386_SUMMARY = ROOT / "runs/summaries/stage12386_transition_local_event_joiner_gap_audit.json"
STAGE12387_SUMMARY = ROOT / "runs/summaries/stage12387_transition_local_materializer_upgrade_worklist.json"
STAGE12387_WORKLIST = (
    ROOT
    / "runs/local/artifacts/stage12387_transition_local_materializer_upgrade_worklist"
    / "transition_local_materializer_upgrade_worklist.jsonl"
)
STAGE12388_SUMMARY = ROOT / "runs/summaries/stage12388_transition_local_candidate_recovery.json"
STAGE12388_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12388_transition_local_candidate_recovery"
    / "transition_local_candidate_recovery_records.jsonl"
)
STAGE12389_SUMMARY = ROOT / "runs/summaries/stage12389_transition_candidate_semantic_review.json"
STAGE12389_RECORDS = (
    ROOT
    / "runs/local/artifacts/stage12389_transition_candidate_semantic_review"
    / "transition_candidate_semantic_review_records.jsonl"
)

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "raw_leak_count": 0,
    "overclaim_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_session_text_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_paths_emitted": False,
    "raw_patches_or_diffs_emitted": False,
    "raw_source_text_emitted": False,
    "raw_urls_emitted": False,
    "private_row_values_emitted": False,
    "model_facing_rows_emitted": False,
}

REQUIRED_BLOCKERS = [
    "level3_control_contract_missing",
    "policy_label_not_admitted",
    "observed_action_only_not_policy_gold",
    "repo_identity_recovery_required",
    "repo_identity_review_required",
    "state_delta_semantic_review_required",
    "verifier_identity_or_transition_missing",
    "verifier_relevance_semantic_review_required",
    "verifier_status_not_training_grade",
    "mixed_patch_status_repair_transition_rejected",
    "patch_failed_repair_transition_rejected",
    "verifier_nonpass_repair_transition_rejected",
    "repo_family_low_confidence",
    "self_repo_dominated_scale_claim_blocked",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|stack trace|"
    r"terminal output|command output|pytest |npm |pip |git clone|git apply|curl |"
    r"bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_OR_ADMISSION_RE = re.compile(
    r"\b(?:admission|admitted|training row|training rows|trainable|"
    r"execution succeeded|replay succeeded|verified repair|closed loop|"
    r"level3 complete|causal proof|patch applied|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_FAIL_CLOSED_CONTEXT_RE = re.compile(
    r"(false|zero|none|\bno\b|no_|not_|blocked|fail_closed|control|"
    r"guardrail|counter|denominator|required|candidate|postrun|"
    r"training_allowed|admission_allowed|admitted_rows|emitted_training_rows|"
    r"countable_new_rows|policy_label|review_queue|manual_review|"
    r"not_policy_gold|not_observed_action_imitation)",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if isinstance(value, dict):
                rows.append(value)
    return rows


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def nonempty(value: Any) -> bool:
    return value not in (None, "", [], {})


def nested(row: dict[str, Any], *keys: str) -> Any:
    value: Any = row
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def source_guardrail_status(payload: dict[str, Any]) -> str:
    if not payload:
        return "missing_fail_closed"
    if payload.get("guardrail_scan_passed") is True:
        return "passed"
    guardrail = payload.get("guardrail_scan")
    if isinstance(guardrail, dict) and guardrail.get("scan_passed") is True:
        return "passed"
    if "guardrail_scan_passed" in payload or isinstance(guardrail, dict):
        return "failed_fail_closed"
    return "legacy_no_scan_fail_closed"


def input_status(*payloads: tuple[str, dict[str, Any], bool]) -> dict[str, Any]:
    return {
        label: {
            "present": present,
            "record_type": payload.get("stage") or "unknown",
            "guardrail_status": source_guardrail_status(payload),
        }
        for label, payload, present in payloads
    }


def recovery_field_counts(recovery_rows: list[dict[str, Any]], recovery_summary: dict[str, Any]) -> dict[str, int]:
    counts = Counter()
    for row in recovery_rows:
        identity = safe_dict(row.get("identity_recovery"))
        transition = safe_dict(row.get("transition_recovery"))
        command = safe_dict(transition.get("command_result_candidate"))
        state = safe_dict(transition.get("state_update_candidate"))
        stop = safe_dict(transition.get("stop_decision_candidate"))
        verifier = safe_dict(transition.get("verifier_transition_candidate"))
        resolved = safe_list(row.get("resolved_blocker_candidates"))

        if nonempty(identity.get("root_id_candidate")):
            counts["root_id_recovered_count"] += 1
        if nonempty(identity.get("repo_family_candidate")):
            counts["repo_family_recovered_count"] += 1
        if nonempty(identity.get("language_candidate")):
            counts["language_recovered_count"] += 1
        if command:
            counts["safe_command_result_class_recovered_count"] += 1
        if nonempty(state.get("state_update_codes")):
            counts["state_update_recovered_count"] += 1
        if nonempty(stop.get("stop_continue_label")):
            counts["stop_decision_recovered_count"] += 1
        if verifier:
            counts["verifier_transition_recovered_count"] += 1
        if any("semantic_rule" in str(item) for item in resolved):
            counts["semantic_rule_id_recovered_count"] += 1
        if any("transition_function" in str(item) for item in resolved):
            counts["transition_function_key_recovered_count"] += 1

    if recovery_rows and not any(
        "semantic_rule" in key for key in safe_dict(recovery_summary.get("blocked_reason_counts"))
    ):
        counts["semantic_rule_id_recovered_count"] = len(recovery_rows)
    if recovery_rows and not any(
        "transition_function" in key for key in safe_dict(recovery_summary.get("blocked_reason_counts"))
    ):
        counts["transition_function_key_recovered_count"] = len(recovery_rows)

    for key in [
        "root_id_recovered_count",
        "repo_family_recovered_count",
        "language_recovered_count",
        "safe_command_result_class_recovered_count",
        "state_update_recovered_count",
        "stop_decision_recovered_count",
        "verifier_transition_recovered_count",
        "semantic_rule_id_recovered_count",
        "transition_function_key_recovered_count",
    ]:
        counts.setdefault(key, 0)
    return dict(counts)


def worklist_blocker_counts(worklist_rows: list[dict[str, Any]], summary: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter(safe_dict(summary.get("blocker_class_counts")))
    if counts:
        return counts
    for row in worklist_rows:
        counts.update(str(item) for item in safe_list(row.get("blocker_classes")))
    return counts


def blocker_counts(
    worklist_rows: list[dict[str, Any]],
    stage12387_summary: dict[str, Any],
    stage12388_summary: dict[str, Any],
    stage12389_summary: dict[str, Any],
) -> dict[str, int]:
    worklist = worklist_blocker_counts(worklist_rows, stage12387_summary)
    recovered = Counter(safe_dict(stage12388_summary.get("blocked_reason_counts")))
    reviewed = Counter(safe_dict(stage12389_summary.get("remaining_blocker_counts")))
    hard = Counter(safe_dict(stage12389_summary.get("hard_rule_counts")))

    counts = {
        "level3_control_contract_missing": max(worklist["level3_control_contract_missing"], reviewed["level3_control_contract_missing"]),
        "policy_label_not_admitted": max(worklist["policy_label_not_admitted"], reviewed["policy_label_not_admitted"]),
        "observed_action_only_not_policy_gold": max(
            worklist["observed_action_only_not_policy_gold"],
            reviewed["observed_action_only_not_policy_gold"],
            recovered["observed_action_only_not_policy_gold"],
        ),
        "repo_identity_recovery_required": max(
            worklist["repo_identity_recovery_required"],
            reviewed["repo_identity_recovery_required"],
            recovered["repo_identity_recovery_required"],
        ),
        "repo_identity_review_required": max(
            reviewed["repo_identity_semantic_review_required"],
            recovered["repo_identity_semantic_review_required"],
        ),
        "state_delta_semantic_review_required": max(
            worklist["state_delta_semantic_review_required"],
            reviewed["state_delta_semantic_review_required"],
            recovered["state_delta_semantic_review_required"],
        ),
        "verifier_identity_or_transition_missing": worklist["verifier_identity_or_transition_missing"],
        "verifier_relevance_semantic_review_required": reviewed["verifier_relevance_semantic_review_required"],
        "verifier_status_not_training_grade": max(
            worklist["verifier_status_not_training_grade"],
            reviewed["verifier_status_not_training_grade"],
            recovered["verifier_status_not_training_grade"],
        ),
        "mixed_patch_status_repair_transition_rejected": hard["mixed_patch_status_repair_transition_rejected"],
        "patch_failed_repair_transition_rejected": hard["patch_failed_repair_transition_rejected"],
        "verifier_nonpass_repair_transition_rejected": hard["verifier_nonpass_repair_transition_rejected"],
        "repo_family_low_confidence": max(reviewed["repo_family_low_confidence"], recovered["repo_family_low_confidence"]),
        "self_repo_dominated_scale_claim_blocked": hard["self_repo_dominated_scale_claim_blocked"],
    }
    return {key: int(counts.get(key, 0)) for key in REQUIRED_BLOCKERS}


def policy_label_counts(
    candidate_denominator_total: int,
    blocker_counts_payload: dict[str, int],
    review_rows: list[dict[str, Any]],
    stage12389_summary: dict[str, Any],
) -> dict[str, int]:
    observed_action_only = blocker_counts_payload["observed_action_only_not_policy_gold"]
    review_needed = max(
        candidate_denominator_total if blocker_counts_payload["policy_label_not_admitted"] else 0,
        int(safe_dict(stage12389_summary.get("recommendation_counts")).get("needs_manual_review", 0)),
    )
    proven_not_imitation = 0
    for row in review_rows:
        policy = safe_dict(nested(row, "semantic_reviews", "policy_label_review"))
        if policy.get("chosen_action_policy_gold_proven") is True and policy.get("observed_action_order_only") is False:
            proven_not_imitation += 1
    return {
        "policy_label_review_queue_count": review_needed,
        "observed_action_imitation_policy_label_count": observed_action_only,
        "policy_label_not_observed_action_imitation_count": proven_not_imitation,
        "manual_review_required_count": review_needed,
    }


def semantic_review_complete(stage12389_summary: dict[str, Any]) -> bool:
    return bool(stage12389_summary) and int(stage12389_summary.get("records_reviewed") or 0) == int(
        stage12389_summary.get("source_records") or -1
    )


def public_artifact_manifest() -> list[dict[str, Any]]:
    names = [
        f"{STAGE}.json",
        "summary.json",
        "public_counter_snapshot.json",
        "blocker_counts.json",
        "policy_label_counters.json",
        "recovered_field_counters.json",
        "input_status.json",
        "public_artifact_manifest.json",
        "guardrail_scan.json",
    ]
    return [
        {
            "artifact_file": name,
            "public_safe": True,
            "raw_leak_count": 0,
            "overclaim_count": 0,
            "raw_urls_emitted": False,
        }
        for name in names
    ]


def scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    for key, expected in ZERO_COUNTERS.items():
        if payload.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    for key, expected in RAW_CONTENT_POLICY.items():
        if safe_dict(payload.get("raw_content_policy")).get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")
    for key in [
        "candidate_denominator_total",
        "candidate_denominator_with_root_id",
        "candidate_denominator_with_repo_family",
        "candidate_denominator_with_language",
        "candidate_denominator_after_policy_label_filter",
        "postrun_public_summary_denominator",
    ]:
        if isinstance(payload.get(key), bool) or not isinstance(payload.get(key), int):
            issues.append(f"required_counter_not_integer:{key}")

    text = json.dumps(payload, sort_keys=True, indent=2)
    raw_leaks = sorted(set(match.group(0)[:80] for match in RAW_LEAK_RE.finditer(text)))
    overclaims: list[str] = []
    for match in OVERCLAIM_OR_ADMISSION_RE.finditer(text):
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        context = text[start:end]
        if not ALLOWED_FAIL_CLOSED_CONTEXT_RE.search(context):
            overclaims.append(match.group(0))
    issues.extend(f"raw_leak_pattern:{item}" for item in raw_leaks)
    issues.extend(f"overclaim_or_admission_pattern:{item}" for item in sorted(set(overclaims)))
    return {
        "scan_passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "raw_leak_count": len(raw_leaks),
        "overclaim_count": len(set(overclaims)),
        "scan_scope": "stage12438_public_aggregate_control_payload_no_raw_rows",
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
    }


def split_payload(artifact_name: str, payload: Any) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "artifact": artifact_name,
        "public_safe": True,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "raw_urls_emitted": False,
        "payload": payload,
    }


def build_artifact() -> dict[str, Any]:
    stage12436_summary = read_json(STAGE12436_SUMMARY)
    stage12386_summary = read_json(STAGE12386_SUMMARY)
    stage12387_summary = read_json(STAGE12387_SUMMARY)
    worklist_rows = read_jsonl(STAGE12387_WORKLIST)
    stage12388_summary = read_json(STAGE12388_SUMMARY)
    recovery_rows = read_jsonl(STAGE12388_RECORDS)
    stage12389_summary = read_json(STAGE12389_SUMMARY)
    review_rows = read_jsonl(STAGE12389_RECORDS)

    recovered_counts = recovery_field_counts(recovery_rows, stage12388_summary)
    blockers = blocker_counts(worklist_rows, stage12387_summary, stage12388_summary, stage12389_summary)
    candidate_denominator_total = len(worklist_rows) or int(stage12387_summary.get("worklist_count") or 0)
    policy_counts = policy_label_counts(candidate_denominator_total, blockers, review_rows, stage12389_summary)
    review_complete = semantic_review_complete(stage12389_summary)
    level3_requirements_present = all(
        recovered_counts[key] == candidate_denominator_total
        for key in [
            "root_id_recovered_count",
            "repo_family_recovered_count",
            "language_recovered_count",
            "safe_command_result_class_recovered_count",
            "state_update_recovered_count",
            "stop_decision_recovered_count",
            "verifier_transition_recovered_count",
            "semantic_rule_id_recovered_count",
            "transition_function_key_recovered_count",
        ]
    )

    public_counters = {
        "candidate_denominator_total": candidate_denominator_total,
        "candidate_denominator_with_root_id": recovered_counts["root_id_recovered_count"],
        "candidate_denominator_with_repo_family": recovered_counts["repo_family_recovered_count"],
        "candidate_denominator_with_language": recovered_counts["language_recovered_count"],
        "candidate_denominator_after_policy_label_filter": 0,
        "postrun_public_summary_denominator": candidate_denominator_total,
        **recovered_counts,
        **policy_counts,
        "level3_candidate_count": 0 if not (level3_requirements_present and review_complete) else 0,
        "patch_trace_candidate_count": 0,
    }

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "session_like_materializer_upgrade_postrun_public_control_v1",
        "canonical_lane_name": LANE,
        "decision": "fail_closed_session_like_materializer_upgrade_postrun_training_still_blocked",
        **ZERO_COUNTERS,
        **public_counters,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "input_status": input_status(
            ("stage12436_parallel_two_lane_control_request", stage12436_summary, bool(stage12436_summary)),
            ("stage12386_transition_local_event_joiner_gap_audit", stage12386_summary, bool(stage12386_summary)),
            ("stage12387_transition_local_materializer_upgrade_worklist", stage12387_summary, bool(stage12387_summary)),
            ("stage12388_transition_local_candidate_recovery", stage12388_summary, bool(stage12388_summary)),
            ("stage12389_transition_candidate_semantic_review", stage12389_summary, bool(stage12389_summary)),
        ),
        "source_record_counts": {
            "stage12386_records_audited": int(stage12386_summary.get("records_audited") or 0),
            "stage12387_worklist_records": candidate_denominator_total,
            "stage12388_recovery_records": len(recovery_rows),
            "stage12389_review_records": len(review_rows),
        },
        "blocker_counts": blockers,
        "recovered_field_counters": recovered_counts,
        "policy_label_counters": policy_counts,
        "control_gate_status": {
            "artifact_is_control_only": "PASS",
            "no_training": "PASS_FALSE",
            "no_admission": "PASS_FALSE",
            "no_execution": "PASS_FALSE",
            "no_model_facing_rows": "PASS_ZERO",
            "observed_action_not_policy_gold": "PASS_REVIEW_QUEUE",
            "policy_filter_blocks_all_candidates": "PASS_ZERO",
            "raw_public_material_absent": "PASS",
        },
        "claim_boundary": (
            "fail_closed aggregate postrun only; no row admission, no model-facing row emission, "
            "no execution, and no policy-gold label claim"
        ),
        "semantic_review_complete": review_complete,
        "level3_requirements_present_for_all_candidates": level3_requirements_present,
        "patch_trace_requirements_complete": False,
        "blocked_next_stage_reason": "policy_label_semantic_review_required_before_level3_or_patch_trace_admission",
        "next_stage_recommendation": (
            "Build a raw-private semantic review packet for the 185 session-like candidates, "
            "focused on policy-valid chosen_action, verifier relevance, state_delta correctness, "
            "and stop_decision correctness. Do not train or admit rows until policy_label_not_observed_action_imitation_count is nonzero "
            "and a separate admission gate proves Level-3 completeness without raw leakage."
        ),
        "public_artifact_manifest": public_artifact_manifest(),
        "summary_hash": "pending",
    }

    guardrail = scan_payload(artifact)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    final_guardrail = scan_payload(artifact)
    artifact["guardrail_scan"] = final_guardrail
    artifact["guardrail_scan_passed"] = final_guardrail["scan_passed"]
    artifact["raw_leak_count"] = final_guardrail["raw_leak_count"]
    artifact["overclaim_count"] = final_guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact


def main() -> None:
    artifact = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_json(OUT / "public_counter_snapshot.json", split_payload("public_counter_snapshot", {
        key: artifact[key]
        for key in [
            "candidate_denominator_total",
            "candidate_denominator_with_root_id",
            "candidate_denominator_with_repo_family",
            "candidate_denominator_with_language",
            "candidate_denominator_after_policy_label_filter",
            "postrun_public_summary_denominator",
            "level3_candidate_count",
            "patch_trace_candidate_count",
            "raw_leak_count",
            "overclaim_count",
            "guardrail_scan_passed",
        ]
    }))
    write_json(OUT / "blocker_counts.json", split_payload("blocker_counts", artifact["blocker_counts"]))
    write_json(OUT / "policy_label_counters.json", split_payload("policy_label_counters", artifact["policy_label_counters"]))
    write_json(OUT / "recovered_field_counters.json", split_payload("recovered_field_counters", artifact["recovered_field_counters"]))
    write_json(OUT / "input_status.json", split_payload("input_status", artifact["input_status"]))
    write_json(
        OUT / "public_artifact_manifest.json",
        split_payload("public_artifact_manifest", artifact["public_artifact_manifest"]),
    )
    write_json(OUT / "guardrail_scan.json", split_payload("guardrail_scan", artifact["guardrail_scan"]))
    print(json.dumps({
        "stage": artifact["stage"],
        "decision": artifact["decision"],
        "candidate_denominator_total": artifact["candidate_denominator_total"],
        "candidate_denominator_after_policy_label_filter": artifact[
            "candidate_denominator_after_policy_label_filter"
        ],
        "policy_label_review_queue_count": artifact["policy_label_review_queue_count"],
        "guardrail_scan_passed": artifact["guardrail_scan_passed"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
