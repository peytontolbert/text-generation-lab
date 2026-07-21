#!/usr/bin/env python3
"""Stage12437 Open-SWE private replay executor pilot-20 request/postrun.

This stage is fail-closed and public-safe. It reads only the Stage12436 public
control summary. If no local public evidence proves that a private executor
already ran, it emits a request/control artifact only: no private rows are
inspected, no checkout or patch application is attempted, no tests are run, no
training rows are emitted, and no admission is allowed.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12437_open_swe_private_replay_executor_pilot_20_request_or_postrun"
OUT = ROOT / "runs/local/artifacts" / STAGE
SUMMARY = ROOT / "runs/summaries" / f"{STAGE}.json"
STAGE12436_SUMMARY = ROOT / "runs/summaries/stage12436_parallel_two_lane_control_request.json"

CANONICAL_LANE = "open_swe_private_replay_executor_pilot_20"
REQUESTED_PRIVATE_CANDIDATE_COUNT = 20

ZERO_COUNTERS: dict[str, bool | int] = {
    "training_allowed": False,
    "admission_allowed": False,
    "execution_allowed": False,
    "admitted_rows": 0,
    "emitted_training_rows": 0,
    "countable_new_rows": 0,
    "proof_complete_candidates": 0,
    "level3_candidates_after_private_replay": 0,
    "patch_trace_candidates": 0,
    "replay_attempted_count": 0,
    "checkout_execution_attempted_count": 0,
    "patch_apply_attempted_count": 0,
    "verifier_execution_attempted_count": 0,
    "tests_run_count": 0,
    "raw_rows_inspected": 0,
    "raw_rows_copied": 0,
    "raw_content_emitted": False,
    "raw_leak_count": 0,
    "overclaim_count": 0,
}

PROOF_SLOT_COUNTERS: dict[str, int | float] = {
    "checkout_before_anchor_proof_count": 0,
    "patch_application_proof_count": 0,
    "same_verifier_before_after_proof_count": 0,
    "causal_transition_proof_count": 0,
    "state_after_anchor_count": 0,
    "stop_continue_anchor_count": 0,
    "distinct_repo_count": 0,
    "duplicate_cluster_max_share": 0.0,
    "proof_complete_candidate_count": 0,
    "level3_candidate_count": 0,
    "patch_trace_candidate_count": 0,
}

RAW_CONTENT_POLICY: dict[str, bool] = {
    "raw_trajectories_emitted": False,
    "raw_commands_emitted": False,
    "raw_outputs_emitted": False,
    "raw_diffs_emitted": False,
    "raw_patches_emitted": False,
    "raw_issue_bodies_emitted": False,
    "raw_paths_emitted": False,
    "raw_urls_emitted": False,
    "urls_emitted": False,
    "source_text_emitted": False,
    "row_values_emitted": False,
    "locator_values_emitted": False,
    "schema_field_names_emitted": True,
    "private_slot_values_emitted": False,
    "training_rows_emitted": False,
    "model_facing_output_emitted": False,
}

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:Traceback \(most recent call last\)|stdout|stderr|stack trace|"
    r"terminal output|command output|pytest |npm |pip |git clone|git apply|"
    r"curl |bash -|sh -|python -c)\b",
    re.IGNORECASE | re.MULTILINE,
)

UNSAFE_OVERCLAIM_RE = re.compile(
    r"\b(?:admission allowed|admitted rows|training rows emitted|trainable rows|"
    r"execution succeeded|private replay succeeded|replay succeeded|verified repair|"
    r"closed loop complete|level3 complete|causal proof complete|patch applied|"
    r"tests passed)\b",
    re.IGNORECASE,
)

ALLOWED_FAIL_CLOSED_CONTEXT_RE = re.compile(
    r"(false|zero|0|none|no_|not_|blocked|fail_closed|request_only|control|"
    r"counter|counters|guardrail|schema|field_names|required|stop_conditions|"
    r"training_allowed|admission_allowed|emitted_training_rows|admitted_rows|"
    r"execution_allowed|raw_content_policy|leak|overclaim|release_requires_future_gate)",
    re.IGNORECASE,
)


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


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return value if isinstance(value, dict) else {}


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return int(value)
    except Exception:
        return 0


def stage12436_guardrail_passed(payload: dict[str, Any]) -> bool:
    if payload.get("guardrail_scan_passed") is True:
        return True
    guardrail = payload.get("guardrail_scan")
    return isinstance(guardrail, dict) and guardrail.get("scan_passed") is True


def source_snapshot(stage12436: dict[str, Any]) -> dict[str, Any]:
    open_contract = safe_dict(stage12436.get("open_swe_lane_contract"))
    lane_counts = safe_dict(safe_dict(stage12436.get("lane_top_level_counts")).get("open_swe_replay_executor_pilot_20"))
    return {
        "source_stage": "stage12436_parallel_two_lane_control_request",
        "source_present": bool(stage12436),
        "source_summary_sha256_24": file_hash(STAGE12436_SUMMARY),
        "source_decision_hash": stable_hash(stage12436.get("decision"), 16),
        "source_guardrail_passed": stage12436_guardrail_passed(stage12436),
        "source_training_allowed": stage12436.get("training_allowed", False),
        "source_admission_allowed": stage12436.get("admission_allowed", False),
        "source_execution_allowed": stage12436.get("execution_allowed", False),
        "source_private_replay_executed": open_contract.get("stage12436_private_replay_executed", False),
        "source_private_rows_inspected": safe_int(open_contract.get("stage12436_private_rows_inspected")),
        "source_candidate_denominator_total": safe_int(stage12436.get("open_swe_metadata_candidate_supply_rows")),
        "source_private_sampled_rows": safe_int(stage12436.get("open_swe_private_sampled_rows")),
        "source_private_dedupe_survivors": safe_int(stage12436.get("open_swe_private_dedupe_survivors")),
        "source_proof_complete_candidates": safe_int(lane_counts.get("proof_complete_candidates")),
        "source_level3_candidates_after_private_replay": safe_int(
            lane_counts.get("level3_candidates_after_private_replay")
        ),
        "source_patch_trace_candidates": safe_int(lane_counts.get("patch_trace_candidates")),
    }


def local_private_execution_evidence(snapshot: dict[str, Any]) -> dict[str, Any]:
    evidence_present = (
        snapshot["source_guardrail_passed"] is True
        and snapshot["source_execution_allowed"] is True
        and snapshot["source_private_replay_executed"] is True
        and snapshot["source_private_rows_inspected"] > 0
    )
    return {
        "private_execution_evidence_present_locally": evidence_present,
        "evidence_mode": "public_aggregate_source_flags_only",
        "private_row_inspection_performed_by_stage12437": False,
        "private_executor_invoked_by_stage12437": False,
        "evidence_absent_reason": ""
        if evidence_present
        else "no_local_public_aggregate_evidence_of_private_replay_execution",
    }


def required_private_inputs() -> dict[str, list[str]]:
    return {
        "candidate_identity_schema_field_names": [
            "candidate_id",
            "dedupe_cluster_id",
            "repository_key",
            "task_key",
        ],
        "checkout_schema_field_names": [
            "checkout_locator",
            "before_anchor",
            "after_anchor",
        ],
        "patch_schema_field_names": [
            "patch_payload",
            "patch_application_status",
        ],
        "verifier_schema_field_names": [
            "verifier_identity",
            "same_verifier_before_after",
            "before_verifier_result",
            "after_verifier_result",
        ],
        "transition_schema_field_names": [
            "causal_transition_evidence",
            "state_after_anchor",
            "stop_continue_label",
        ],
    }


def required_executor_outputs() -> dict[str, list[str]]:
    return {
        "aggregate_counter_field_names": [
            "executed_candidate_denominator",
            "checkout_before_anchor_proof_count",
            "patch_application_proof_count",
            "same_verifier_before_after_proof_count",
            "causal_transition_proof_count",
            "state_after_anchor_count",
            "stop_continue_anchor_count",
            "distinct_repo_count",
            "duplicate_cluster_max_share",
            "proof_complete_candidate_count",
            "level3_candidate_count",
            "patch_trace_candidate_count",
            "raw_leak_count",
            "overclaim_count",
        ],
        "per_candidate_schema_field_names": [
            "candidate_id_hash",
            "execution_status_enum",
            "checkout_before_anchor_proof_present",
            "patch_application_proof_present",
            "same_verifier_before_after_proof_present",
            "causal_transition_proof_present",
            "state_after_anchor_present",
            "stop_continue_anchor_present",
            "public_error_class",
        ],
    }


def stop_conditions() -> list[str]:
    return [
        "raw_url_path_diff_patch_command_output_or_private_locator_value_leakage",
        "raw_private_row_value_emitted",
        "raw_private_schema_value_emitted_instead_of_field_name",
        "unqualified_overclaim_or_admission_language",
        "source_stage12436_guardrail_not_passed",
        "source_stage12436_training_allowed_not_false",
        "source_stage12436_admission_allowed_not_false",
        "source_stage12436_execution_allowed_not_false_for_request_only",
        "stage12437_execution_allowed_not_false_without_private_evidence",
        "stage12437_training_allowed_not_false",
        "stage12437_admission_allowed_not_false",
        "stage12437_admitted_rows_nonzero",
        "stage12437_emitted_training_rows_nonzero",
        "stage12437_countable_new_rows_nonzero",
        "stage12437_replay_attempted_without_explicit_private_executor",
        "stage12437_checkout_or_patch_or_verifier_attempted_without_explicit_private_executor",
        "stage12437_tests_run_nonzero",
        "requested_private_candidate_count_not_20",
        "canonical_lane_name_mismatch",
        "proof_slot_counter_nonzero_without_execution_evidence",
    ]


def public_artifact_manifest() -> list[dict[str, Any]]:
    names = [
        f"{STAGE}.json",
        "summary.json",
        "source_accounting_snapshot.json",
        "request_contract.json",
        "public_proof_slot_counters.json",
        "required_private_inputs.json",
        "required_executor_outputs.json",
        "stop_conditions.json",
        "guardrail_scan.json",
    ]
    return [
        {
            "artifact_file": name,
            "public_safe": True,
            "raw_leak_count": 0,
            "overclaim_count": 0,
            "raw_urls_emitted": False,
            "urls_emitted": False,
        }
        for name in names
    ]


def split_payload(artifact_name: str, payload: Any) -> dict[str, Any]:
    return {
        "stage": STAGE,
        "artifact": artifact_name,
        "public_safe": True,
        "raw_leak_count": 0,
        "overclaim_count": 0,
        "raw_urls_emitted": False,
        "urls_emitted": False,
        "payload": payload,
    }


def scan_payload(payload: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    for key, expected in ZERO_COUNTERS.items():
        if payload.get(key) != expected:
            issues.append(f"zero_counter_mismatch:{key}")
    for key, expected in PROOF_SLOT_COUNTERS.items():
        if payload.get(key) != expected:
            issues.append(f"proof_slot_counter_mismatch:{key}")
    raw_policy = safe_dict(payload.get("raw_content_policy"))
    for key, expected in RAW_CONTENT_POLICY.items():
        if raw_policy.get(key) != expected:
            issues.append(f"raw_content_policy_mismatch:{key}")
    if payload.get("canonical_lane_name") != CANONICAL_LANE:
        issues.append("canonical_lane_name_mismatch")
    if payload.get("requested_private_candidate_count") != REQUESTED_PRIVATE_CANDIDATE_COUNT:
        issues.append("requested_private_candidate_count_mismatch")
    if payload.get("decision") != "fail_closed_private_replay_executor_request_only_no_execution":
        issues.append("decision_not_request_only_fail_closed")
    if payload.get("private_execution_evidence_present_locally") is not False:
        issues.append("private_execution_evidence_present_for_request_only_artifact")
    if payload.get("guardrail_scan_passed") is not None:
        issues.append("guardrail_scan_passed_set_before_scan_finalization")

    for item in payload.get("public_artifact_manifest", []):
        if not isinstance(item, dict):
            issues.append("public_artifact_manifest_item_not_object")
            continue
        if item.get("raw_leak_count") != 0:
            issues.append(f"public_artifact_raw_leak_count_nonzero:{item.get('artifact_file')}")
        if item.get("overclaim_count") != 0:
            issues.append(f"public_artifact_overclaim_count_nonzero:{item.get('artifact_file')}")
        if item.get("raw_urls_emitted") is not False:
            issues.append(f"public_artifact_raw_urls_emitted_not_false:{item.get('artifact_file')}")
        if item.get("urls_emitted") is not False:
            issues.append(f"public_artifact_urls_emitted_not_false:{item.get('artifact_file')}")

    text = json.dumps(payload, sort_keys=True, indent=2)
    raw_leaks = sorted(set(match.group(0)[:80] for match in RAW_LEAK_RE.finditer(text)))
    overclaims: list[str] = []
    for match in UNSAFE_OVERCLAIM_RE.finditer(text):
        start = max(0, match.start() - 120)
        end = min(len(text), match.end() + 120)
        context = text[start:end]
        if not ALLOWED_FAIL_CLOSED_CONTEXT_RE.search(context):
            overclaims.append(match.group(0).lower())
    issues.extend(f"raw_leak_pattern:{item}" for item in raw_leaks)
    issues.extend(f"overclaim_or_admission_pattern:{item}" for item in sorted(set(overclaims)))
    return {
        "scan_passed": not issues,
        "issue_count": len(issues),
        "issues": issues,
        "raw_leak_count": len(raw_leaks),
        "overclaim_count": len(set(overclaims)),
        "scan_scope": "stage12437_public_request_control_payload_no_private_rows_no_execution",
        "zero_counter_keys_checked": sorted(ZERO_COUNTERS),
        "proof_slot_counter_keys_checked": sorted(PROOF_SLOT_COUNTERS),
        "raw_content_policy_keys_checked": sorted(RAW_CONTENT_POLICY),
        "leak_patterns_checked": [
            "url_like",
            "absolute_path_like",
            "diff_or_patch_hunk_like",
            "shell_command_like",
            "command_output_like",
            "private_locator_value_like",
        ],
        "overclaim_patterns_checked": [
            "admission_allowed",
            "admitted_rows",
            "training_rows_emitted",
            "execution_succeeded",
            "private_replay_succeeded",
            "verified_repair",
            "closed_loop_complete",
            "level3_complete",
            "causal_proof_complete",
            "patch_applied",
            "tests_passed",
        ],
        "schema_field_names_only_exception": [
            "required_private_inputs",
            "required_executor_outputs",
        ],
    }


def build_artifact() -> dict[str, Any]:
    stage12436 = read_json(STAGE12436_SUMMARY)
    snapshot = source_snapshot(stage12436)
    evidence = local_private_execution_evidence(snapshot)

    decision = (
        "private_replay_executor_postrun_public_summary"
        if evidence["private_execution_evidence_present_locally"]
        else "fail_closed_private_replay_executor_request_only_no_execution"
    )
    if decision != "fail_closed_private_replay_executor_request_only_no_execution":
        raise RuntimeError("Stage12437 is configured to fail closed unless local private execution evidence is absent.")

    request_contract = {
        "record_type": "open_swe_private_replay_executor_pilot_20_request_contract_v1",
        "canonical_lane_name": CANONICAL_LANE,
        "requested_private_candidate_count": REQUESTED_PRIVATE_CANDIDATE_COUNT,
        "maximum_candidates_to_execute": REQUESTED_PRIVATE_CANDIDATE_COUNT,
        "execution_mode": "request_only_no_execution",
        "public_output_mode": "aggregate_counts_only",
        "raw_private_material_public_output_allowed": False,
        "schema_field_names_allowed": True,
        "private_row_values_allowed": False,
        "release_policy": {
            "training_allowed_after_stage12437": False,
            "admission_allowed_after_stage12437": False,
            "admission_release_requires_future_gate": True,
        },
    }

    artifact: dict[str, Any] = {
        "stage": STAGE,
        "record_type": "open_swe_private_replay_executor_pilot_20_request_or_postrun_v1",
        "decision": decision,
        "selected_path": "request_only_no_private_execution_evidence",
        "canonical_lane_name": CANONICAL_LANE,
        "requested_lane_canonical_name": CANONICAL_LANE,
        "requested_private_candidate_count": REQUESTED_PRIVATE_CANDIDATE_COUNT,
        "candidate_denominator_total": snapshot["source_candidate_denominator_total"],
        "candidate_denominator_after_dedupe": snapshot["source_private_dedupe_survivors"],
        "source_private_sampled_rows": snapshot["source_private_sampled_rows"],
        "requested_candidate_denominator": REQUESTED_PRIVATE_CANDIDATE_COUNT,
        "selected_candidate_denominator": 0,
        "executed_candidate_denominator": 0,
        "postrun_public_summary_denominator": 0,
        **ZERO_COUNTERS,
        **PROOF_SLOT_COUNTERS,
        **evidence,
        "source_accounting_snapshot": snapshot,
        "request_contract": request_contract,
        "required_private_inputs": required_private_inputs(),
        "required_executor_outputs": required_executor_outputs(),
        "stop_conditions": stop_conditions(),
        "raw_content_policy": RAW_CONTENT_POLICY,
        "public_artifact_manifest": public_artifact_manifest(),
        "guardrail_scan_passed": None,
        "control_gate_status": {
            "artifact_is_request_only": "PASS",
            "private_execution_evidence_present_locally": "PASS_FALSE",
            "private_executor_invoked_by_stage12437": "PASS_FALSE",
            "private_rows_inspected_by_stage12437": "PASS_FALSE",
            "training_allowed_false": "PASS",
            "admission_allowed_false": "PASS",
            "execution_allowed_false": "PASS",
            "no_rows_admitted": "PASS",
            "no_training_rows_emitted": "PASS",
            "proof_slot_counters_zero_without_execution": "PASS",
            "canonical_lane_name": CANONICAL_LANE,
            "requested_private_candidate_count": REQUESTED_PRIVATE_CANDIDATE_COUNT,
        },
        "next_action_request": {
            "executor_lane": CANONICAL_LANE,
            "requested_private_candidate_count": REQUESTED_PRIVATE_CANDIDATE_COUNT,
            "private_executor_required": True,
            "public_summary_required": True,
            "raw_private_values_publicly_allowed": False,
            "training_allowed": False,
            "admission_allowed": False,
        },
    }

    guardrail_input = dict(artifact)
    guardrail = scan_payload(guardrail_input)
    artifact["guardrail_scan"] = guardrail
    artifact["guardrail_scan_passed"] = guardrail["scan_passed"]
    artifact["raw_leak_count"] = guardrail["raw_leak_count"]
    artifact["overclaim_count"] = guardrail["overclaim_count"]
    artifact["summary_hash"] = stable_hash({k: v for k, v in artifact.items() if k != "summary_hash"})
    return artifact


def main() -> None:
    artifact = build_artifact()
    write_json(OUT / f"{STAGE}.json", artifact)
    write_json(OUT / "summary.json", artifact)
    write_json(SUMMARY, artifact)
    write_json(OUT / "source_accounting_snapshot.json", split_payload("source_accounting_snapshot", artifact["source_accounting_snapshot"]))
    write_json(OUT / "request_contract.json", split_payload("request_contract", artifact["request_contract"]))
    write_json(OUT / "public_proof_slot_counters.json", split_payload("public_proof_slot_counters", PROOF_SLOT_COUNTERS))
    write_json(OUT / "required_private_inputs.json", split_payload("required_private_inputs", artifact["required_private_inputs"]))
    write_json(OUT / "required_executor_outputs.json", split_payload("required_executor_outputs", artifact["required_executor_outputs"]))
    write_json(OUT / "stop_conditions.json", split_payload("stop_conditions", artifact["stop_conditions"]))
    write_json(OUT / "guardrail_scan.json", split_payload("guardrail_scan", artifact["guardrail_scan"]))
    print(json.dumps(artifact, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
