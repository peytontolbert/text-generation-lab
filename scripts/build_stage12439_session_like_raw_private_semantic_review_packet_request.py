#!/usr/bin/env python3
"""Build Stage12439 public-safe request/control artifacts.

This stage requests future raw-private semantic review packets for the
Stage12438 session-like candidates. It is public/control only: it does not
inspect raw rows, copy raw values, execute review, admit rows, or train.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12439_session_like_raw_private_semantic_review_packet_request"
LANE = "session_like_materializer_upgrade"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12438_SUMMARY = ROOT / "runs/summaries/stage12438_session_like_materializer_upgrade_postrun.json"
STAGE12436_SUMMARY = ROOT / "runs/summaries/stage12436_parallel_two_lane_control_request.json"
STAGE12389_SUMMARY = ROOT / "runs/summaries/stage12389_transition_candidate_semantic_review.json"

REQUESTED_REVIEW_CANDIDATE_COUNT = 185
STRUCTURALLY_RECOVERED_CANDIDATE_COUNT = 94

REQUIRED_PRIVATE_REVIEW_SLOTS = [
    "policy_valid_chosen_action",
    "verifier_relevance",
    "state_delta_correctness",
    "stop_decision_correctness",
    "repo_identity_validity",
    "same_source_lineage",
    "raw_evidence_sufficiency",
]

PUBLIC_REVIEW_PACKET_SCHEMA_FIELD_NAMES = [
    "candidate_request_id",
    "candidate_public_fingerprint",
    "candidate_sequence_ordinal",
    "requested_private_review_slots",
    "policy_valid_chosen_action",
    "verifier_relevance",
    "state_delta_correctness",
    "stop_decision_correctness",
    "repo_identity_validity",
    "same_source_lineage",
    "raw_evidence_sufficiency",
    "observed_action_imitation",
    "chosen_action_policy_valid",
    "state_delta_correct",
    "stop_decision_correct",
    "no_raw_leak",
    "protected_overlap_absent",
    "reviewer_decision",
    "reviewer_notes_redacted",
]

FUTURE_ACCEPTANCE_RULES = {
    "accepted_only_if": {
        "observed_action_imitation": False,
        "chosen_action_policy_valid": True,
        "verifier_relevance": True,
        "state_delta_correct": True,
        "stop_decision_correct": True,
        "same_source_lineage": True,
        "no_raw_leak": True,
        "protected_overlap_absent": True,
    },
    "release_requires_separate_future_gate": True,
    "stage12439_admission_allowed": False,
    "stage12439_training_allowed": False,
}

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "level3_candidate_count": 0,
    "patch_trace_candidate_count": 0,
    "candidate_denominator_with_private_review_packet": 0,
    "review_ready_count": 0,
    "review_accepted_count": 0,
    "review_rejected_count": 0,
    "review_deferred_count": 0,
    "raw_private_review_executed_by_stage12439": False,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "candidate_denominator_after_policy_label_filter": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_session_text_emitted": False,
    "raw_url_values_emitted": False,
    "raw_path_values_emitted": False,
    "raw_diff_values_emitted": False,
    "raw_patch_values_emitted": False,
    "raw_command_values_emitted": False,
    "raw_output_values_emitted": False,
    "raw_source_values_emitted": False,
    "private_locator_values_emitted": False,
    "private_row_values_emitted": False,
    "model_facing_rows_emitted": False,
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout:|stderr:|stack trace|"
    r"terminal output:|command output:|pytest\s+\S|npm\s+\S|pip\s+\S|"
    r"git clone\s+\S|git apply\s+\S|curl\s+\S|bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

OVERCLAIM_OR_ADMISSION_RE = re.compile(
    r"\b(?:admission|admitted|training|trainable|accepted|acceptance|"
    r"proof|execution succeeded|review executed|verified repair|closed loop|"
    r"level3 complete|level-3|patch-trace|patch applied|tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_FAIL_CLOSED_CONTEXT_RE = re.compile(
    r"(false|0|zero|none|\bno\b|no_|not_|blocked|fail_closed|control|"
    r"guardrail|counter|denominator|required|candidate|request|only_if|"
    r"release_requires|future|separate_future_gate|stage12439_|allowed|"
    r"training_allowed|admission_allowed|admitted_rows|emitted_training_rows|"
    r"countable_new_rows|proof_floor|summary|policy_label|"
    r"observed_action_imitation|protected_overlap_absent)",
    re.IGNORECASE,
)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


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


def input_status(*payloads: tuple[str, Path, dict[str, Any]]) -> dict[str, Any]:
    return {
        label: {
            "present": bool(payload),
            "record_type": payload.get("record_type") or payload.get("stage") or "unknown",
            "guardrail_status": source_guardrail_status(payload),
            "summary_sha256_24": file_hash(path),
        }
        for label, path, payload in payloads
    }


def artifact_manifest() -> list[dict[str, Any]]:
    names = [
        f"{STAGE}.json",
        "summary.json",
        "request_control.json",
        "public_review_packet_schema.json",
        "future_acceptance_rules.json",
        "blocker_counts.json",
        "input_status.json",
        "guardrail_scan.json",
        "public_artifact_manifest.json",
    ]
    return [
        {
            "artifact_file": name,
            "public_safe": True,
            "contains_raw_values": False,
            "raw_leak_count": 0,
            "overclaim_count": 0,
        }
        for name in names
    ]


def split_payload(artifact_name: str, payload: Any) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "artifact": artifact_name,
        "public_safe": True,
        "contains_raw_values": False,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "payload": payload,
    }


def scan_single_payload(label: str, payload: Any) -> list[str]:
    issues: list[str] = []
    text = json.dumps(payload, sort_keys=True, indent=2)
    for match in RAW_LEAK_RE.finditer(text):
        issues.append(f"{label}:raw_leak_pattern:{match.group(0)[:80]}")
    for match in OVERCLAIM_OR_ADMISSION_RE.finditer(text):
        start = max(0, match.start() - 140)
        end = min(len(text), match.end() + 140)
        context = text[start:end]
        if not ALLOWED_FAIL_CLOSED_CONTEXT_RE.search(context):
            issues.append(f"{label}:overclaim_or_admission_pattern:{match.group(0)}")
    return issues


def scan_artifact_set(artifact_set: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    main = safe_dict(artifact_set.get("main"))
    for key, expected in ZERO_COUNTERS.items():
        if main.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    for key, expected in RAW_CONTENT_POLICY.items():
        if safe_dict(main.get("raw_content_policy")).get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")
    if main.get("requested_review_candidate_count") != REQUESTED_REVIEW_CANDIDATE_COUNT:
        issues.append("requested_review_candidate_count_mismatch")
    if main.get("structurally_recovered_candidate_count") != STRUCTURALLY_RECOVERED_CANDIDATE_COUNT:
        issues.append("structurally_recovered_candidate_count_mismatch")
    if main.get("candidate_denominator_missing_private_review_packet") != REQUESTED_REVIEW_CANDIDATE_COUNT:
        issues.append("candidate_denominator_missing_private_review_packet_mismatch")
    for key in [
        "candidate_denominator_policy_review_requested",
        "candidate_denominator_verifier_relevance_review_requested",
        "candidate_denominator_state_delta_review_requested",
        "candidate_denominator_stop_decision_review_requested",
    ]:
        if main.get(key) != REQUESTED_REVIEW_CANDIDATE_COUNT:
            issues.append(f"{key}_mismatch")
    if main.get("public_review_packet_schema") != PUBLIC_REVIEW_PACKET_SCHEMA_FIELD_NAMES:
        issues.append("public_review_packet_schema_not_field_names_only")
    if main.get("required_private_review_slots") != REQUIRED_PRIVATE_REVIEW_SLOTS:
        issues.append("required_private_review_slots_mismatch")

    for label, payload in artifact_set.items():
        if label == "guardrail_scan":
            continue
        issues.extend(scan_single_payload(label, payload))

    raw_leak_issues = [issue for issue in issues if ":raw_leak_pattern:" in issue]
    overclaim_issues = [issue for issue in issues if ":overclaim_or_admission_pattern:" in issue]
    return {
        "scan_passed": not issues,
        "issue_count": len(issues),
        "issues": sorted(set(issues)),
        "raw_leak_count": len(set(raw_leak_issues)),
        "overclaim_count": len(set(overclaim_issues)),
        "scan_scope": "stage12439_public_request_control_artifact_set_no_raw_rows",
        "raw_leak_policy": {
            "raw_url_value_leak_fails": True,
            "raw_path_value_leak_fails": True,
            "raw_diff_or_patch_body_leak_fails": True,
            "raw_command_text_leak_fails": True,
            "raw_output_text_leak_fails": True,
            "raw_source_text_leak_fails": True,
            "private_locator_value_leak_fails": True,
        },
        "overclaim_policy": {
            "unqualified_admission_claim_fails": True,
            "unqualified_training_claim_fails": True,
            "unqualified_proof_claim_fails": True,
        },
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
    }


def build_artifact() -> dict[str, Any]:
    stage12438 = read_json(STAGE12438_SUMMARY)
    stage12436 = read_json(STAGE12436_SUMMARY)
    stage12389 = read_json(STAGE12389_SUMMARY)

    blocker_counts = safe_dict(stage12438.get("blocker_counts"))
    source_record_counts = safe_dict(stage12438.get("source_record_counts"))

    schema_contract = {
        "schema_values_publicly_emitted": False,
        "field_names_only": True,
        "field_names": PUBLIC_REVIEW_PACKET_SCHEMA_FIELD_NAMES,
        "raw_value_columns_must_be_private": True,
        "public_packet_row_values_allowed": False,
    }

    request_control = {
        "request_candidate_count": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "structurally_recovered_candidate_count": STRUCTURALLY_RECOVERED_CANDIDATE_COUNT,
        "private_review_packet_presence_count": 0,
        "private_review_packet_missing_count": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_after_policy_label_filter": 0,
        "candidate_denominator_policy_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_verifier_relevance_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_state_delta_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_stop_decision_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "review_execution_requested_for_future_stage": True,
        "review_execution_performed_here": False,
        "review_ready_count": 0,
        "review_accepted_count": 0,
        "review_rejected_count": 0,
        "review_deferred_count": 0,
        "policy_label_not_observed_action_imitation_count": 0,
        "observed_action_imitation_policy_label_count": 0,
        "required_private_review_slots": REQUIRED_PRIVATE_REVIEW_SLOTS,
        "public_schema_field_names_only": PUBLIC_REVIEW_PACKET_SCHEMA_FIELD_NAMES,
        "no_training_or_admission_release_by_this_artifact": True,
    }

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "raw_private_semantic_review_packet_request_public_control_v1",
        "decision": "fail_closed_raw_private_semantic_review_packet_request_only",
        "canonical_lane_name": LANE,
        "requested_review_candidate_count": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "structurally_recovered_candidate_count": STRUCTURALLY_RECOVERED_CANDIDATE_COUNT,
        **ZERO_COUNTERS,
        "candidate_denominator_with_private_review_packet": 0,
        "candidate_denominator_missing_private_review_packet": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_structurally_recovered": STRUCTURALLY_RECOVERED_CANDIDATE_COUNT,
        "review_ready_count": 0,
        "review_accepted_count": 0,
        "review_rejected_count": 0,
        "review_deferred_count": 0,
        "policy_label_not_observed_action_imitation_count": 0,
        "observed_action_imitation_policy_label_count": 0,
        "candidate_denominator_policy_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_verifier_relevance_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_state_delta_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "candidate_denominator_stop_decision_review_requested": REQUESTED_REVIEW_CANDIDATE_COUNT,
        "required_private_review_slots": REQUIRED_PRIVATE_REVIEW_SLOTS,
        "public_review_packet_schema": PUBLIC_REVIEW_PACKET_SCHEMA_FIELD_NAMES,
        "public_review_packet_schema_contract": schema_contract,
        "future_acceptance_rules": FUTURE_ACCEPTANCE_RULES,
        "blocker_counts": blocker_counts,
        "source_public_counter_snapshot": {
            "stage12438_candidate_denominator_total": int(stage12438.get("candidate_denominator_total") or 0),
            "stage12438_candidate_denominator_after_policy_label_filter": int(
                stage12438.get("candidate_denominator_after_policy_label_filter") or 0
            ),
            "stage12438_policy_label_review_queue_count": int(stage12438.get("policy_label_review_queue_count") or 0),
            "stage12438_observed_action_imitation_policy_label_count": int(
                stage12438.get("observed_action_imitation_policy_label_count") or 0
            ),
            "stage12389_records_reviewed": int(stage12389.get("records_reviewed") or 0),
            "stage12389_source_records": int(stage12389.get("source_records") or 0),
        },
        "source_record_counts": source_record_counts,
        "raw_content_policy": RAW_CONTENT_POLICY,
        "input_status": input_status(
            ("stage12438_session_like_materializer_upgrade_postrun", STAGE12438_SUMMARY, stage12438),
            ("stage12436_parallel_two_lane_control_request", STAGE12436_SUMMARY, stage12436),
            ("stage12389_transition_candidate_semantic_review", STAGE12389_SUMMARY, stage12389),
        ),
        "request_control": request_control,
        "control_gate_status": {
            "artifact_is_request_only": "PASS",
            "raw_private_review_executed_by_stage12439": "PASS_FALSE",
            "raw_rows_inspected": "PASS_ZERO",
            "raw_rows_copied": "PASS_ZERO",
            "training_allowed": "PASS_FALSE",
            "admission_allowed": "PASS_FALSE",
            "execution_allowed": "PASS_FALSE",
            "candidate_denominator_after_policy_label_filter": "PASS_ZERO",
            "candidate_denominator_with_private_review_packet": "PASS_ZERO",
            "candidate_denominator_missing_private_review_packet": "PASS_185",
            "review_ready_count": "PASS_ZERO",
            "review_outcome_counts": "PASS_ZERO",
            "public_review_packet_schema_values": "PASS_FIELD_NAMES_ONLY",
        },
        "next_stage_recommendation": "stage12440_session_like_raw_private_semantic_review_postrun",
        "claim_boundary": (
            "public request/control artifact only; no raw-private review execution, no row admission, "
            "no training emission, no raw value copying, and no policy-valid chosen_action claim"
        ),
        "public_artifact_manifest": artifact_manifest(),
        "summary_hash": "pending",
    }

    split_artifacts = {
        "main": artifact,
        "request_control": split_payload("request_control", request_control),
        "public_review_packet_schema": split_payload("public_review_packet_schema", schema_contract),
        "future_acceptance_rules": split_payload("future_acceptance_rules", FUTURE_ACCEPTANCE_RULES),
        "blocker_counts": split_payload("blocker_counts", blocker_counts),
        "input_status": split_payload("input_status", artifact["input_status"]),
        "public_artifact_manifest": split_payload("public_artifact_manifest", artifact["public_artifact_manifest"]),
    }
    guardrail = scan_artifact_set(split_artifacts)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})

    split_artifacts["main"] = artifact
    guardrail = scan_artifact_set(split_artifacts)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact


def main() -> None:
    artifact = build_artifact()
    OUT.mkdir(parents=True, exist_ok=True)
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_json(OUT / "request_control.json", split_payload("request_control", artifact["request_control"]))
    write_json(
        OUT / "public_review_packet_schema.json",
        split_payload("public_review_packet_schema", artifact["public_review_packet_schema_contract"]),
    )
    write_json(OUT / "future_acceptance_rules.json", split_payload("future_acceptance_rules", artifact["future_acceptance_rules"]))
    write_json(OUT / "blocker_counts.json", split_payload("blocker_counts", artifact["blocker_counts"]))
    write_json(OUT / "input_status.json", split_payload("input_status", artifact["input_status"]))
    write_json(OUT / "guardrail_scan.json", split_payload("guardrail_scan", artifact["guardrail_scan"]))
    write_json(
        OUT / "public_artifact_manifest.json",
        split_payload("public_artifact_manifest", artifact["public_artifact_manifest"]),
    )
    print(
        json.dumps(
            {
                "stage": artifact["stage"],
                "decision": artifact["decision"],
                "requested_review_candidate_count": artifact["requested_review_candidate_count"],
                "structurally_recovered_candidate_count": artifact["structurally_recovered_candidate_count"],
                "candidate_denominator_after_policy_label_filter": artifact[
                    "candidate_denominator_after_policy_label_filter"
                ],
                "guardrail_scan_passed": artifact["guardrail_scan_passed"],
                "raw_leak_count": artifact["raw_leak_count"],
                "overclaim_count": artifact["overclaim_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
