#!/usr/bin/env python3
"""Build Stage12464 fail-closed Bears source acquisition/hydration repair request.

This stage emits a request only. It does not use network, checkout source,
initialize submodules, run tests, train, package, or admit rows.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12464_bears_source_acquisition_or_hydration_repair_request"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
REQUEST_OUT = OUT_DIR / "source_acquisition_or_hydration_repair_request.json"
WORK_ITEMS_OUT = OUT_DIR / "bears_hydration_repair_work_items.jsonl"
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12463_SUMMARY = (
    ROOT / "runs/summaries/stage12463_bears_executor_feasibility_and_blocker_audit.json"
)
STAGE12462_SUMMARY = (
    ROOT / "runs/summaries/stage12462_bears_private_proof_slot_executor_work_order.json"
)
STAGE12462_ITEMS = (
    ROOT
    / "runs/local/artifacts/stage12462_bears_private_proof_slot_executor_work_order"
    / "executor_work_items.jsonl"
)
STAGE12333_SUMMARY = (
    ROOT
    / "runs/local/artifacts/stage12333_bears_hydration_request"
    / "bears_hydration_request_summary.json"
)
STAGE12336_AUDIT = (
    ROOT
    / "runs/local/artifacts/stage12336_bears_local_hydration_blocker_audit"
    / "bears_local_hydration_blocker_audit.json"
)
STAGE12327_CANDIDATES = (
    ROOT
    / "runs/local/artifacts/stage12327_external_adapter_preflight"
    / "bears_failing_passing_candidates.jsonl"
)

EXPECTED_REQUEST_COUNT = 19
EXPECTED_GAP = 15
LANGUAGE_BUCKET = "single_jvm_java_only_not_multilingual_coverage"
PRIMARY_BLOCKERS = [
    "missing_submodule_or_git",
    "missing_checkout",
    "missing_verifier_command_output",
    "missing_patch_lineage",
    "missing_same_source_causality",
]
ACQUISITION_ACTIONS_REQUESTED = [
    "source_submodule_initialization_or_authoritative_source_bundle",
    "verifier_command_output_join",
    "patch_lineage_join",
    "same_source_causality_join",
]
REQUIRED_MISSING_PROOF_SLOTS = [
    "buggy_checkout_content_availability",
    "fixed_checkout_content_availability",
    "buggy_verifier_fail",
    "fixed_or_before_plus_patch_verifier_pass",
    "exact_same_verifier_identity",
    "patch_diff_apply_lineage",
    "verifier_relevance",
    "same_source_lineage",
    "source_test_hashes",
    "ordered_patch_effect_causality",
]

RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:stdout|stderr|traceback|terminal output|command output|git clone|"
    r"git apply|pytest\s|python -c|bash -|sh -|curl\s)\b|"
    r"\b[0-9a-f]{40}\b",
    re.IGNORECASE | re.MULTILINE,
)
FORBIDDEN_PUBLIC_KEYS = {
    "repo",
    "repo_family",
    "repo_id",
    "repo_name",
    "path",
    "paths",
    "url",
    "urls",
    "uri",
    "command",
    "commands",
    "stdout",
    "stderr",
    "diff",
    "patch",
    "patch_body",
    "raw_text",
    "source",
    "source_text",
    "file_content",
    "content",
}
KEY_ALLOW_RE = re.compile(
    r"(hash|hashes|ref|refs|schema|slot|slots|blocker|scan|policy|request)",
    re.IGNORECASE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no} must contain a JSON object")
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


def scan_public(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not KEY_ALLOW_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(scan_public(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(scan_public(f"{label}[{index}]", child))
    return issues


def validate_inputs(
    stage12463: dict[str, Any],
    stage12462: dict[str, Any],
    work_items: list[dict[str, Any]],
) -> list[str]:
    blockers: list[str] = []
    if stage12462.get("request_count") != len(work_items):
        blockers.append("stage12462_work_order_count_mismatch")
    if stage12463.get("work_order_request_count") != len(work_items):
        blockers.append("stage12463_work_order_count_mismatch")
    if len(work_items) != EXPECTED_REQUEST_COUNT:
        blockers.append("stage12462_work_order_not_current_19")
    for key in [
        "training_allowed",
        "admission_allowed",
        "packaging_allowed",
        "execution_performed_by_stage",
    ]:
        if stage12462.get(key) is not False:
            blockers.append(f"stage12462_{key}_not_false")
        if stage12463.get(key) is not False:
            blockers.append(f"stage12463_{key}_not_false")
    if stage12462.get("guardrail_scan_passed") is not True:
        blockers.append("stage12462_guardrail_not_passed")
    if stage12463.get("guardrail_scan_passed") is not True:
        blockers.append("stage12463_guardrail_not_passed")
    for blocker in PRIMARY_BLOCKERS:
        if stage12463.get("blocker_counts", {}).get(blocker) != len(work_items):
            blockers.append(f"stage12463_{blocker}_count_mismatch")
    return blockers


def build_work_items(work_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in work_items:
        rows.append(
            {
                "record_type": "stage12464_bears_hydration_repair_work_item_hash_only_v1",
                "stage": STAGE,
                "priority_rank": item["priority_rank"],
                "work_order_item_ref_hash": item["work_order_item_ref_hash"],
                "candidate_ref_hash": item["candidate_ref_hash"],
                "language_bucket": LANGUAGE_BUCKET,
                "required_missing_proof_slots": REQUIRED_MISSING_PROOF_SLOTS,
                "primary_blockers": PRIMARY_BLOCKERS,
                "acquisition_actions_requested": ACQUISITION_ACTIONS_REQUESTED,
                "executor_after_acquisition_allowed": False,
                "training_allowed": False,
                "admission_allowed": False,
                "packaging_allowed": False,
                "execution_performed_by_stage": False,
                "external_comparable_repair_credit_count": 0,
                "emitted_training_rows": 0,
                "sealed_eval_rows": 0,
                "public_raw_leak_guardrail": {
                    "hash_only": True,
                    "raw_repo_names_paths_urls_commands_outputs_diffs_source_text": False,
                },
                "request_item_ref_hash": stable_hash(
                    {
                        "work_order_item_ref_hash": item["work_order_item_ref_hash"],
                        "candidate_ref_hash": item["candidate_ref_hash"],
                        "priority_rank": item["priority_rank"],
                    }
                ),
            }
        )
    return rows


def main() -> None:
    required_paths = [
        STAGE12463_SUMMARY,
        STAGE12462_SUMMARY,
        STAGE12462_ITEMS,
        STAGE12333_SUMMARY,
        STAGE12336_AUDIT,
        STAGE12327_CANDIDATES,
    ]
    missing = [path.name for path in required_paths if not path.exists()]
    if missing:
        summary = {
            "record_type": "stage12464_bears_source_acquisition_or_hydration_repair_request_summary_v1",
            "stage": STAGE,
            "decision": "blocked_missing_prior_work_order",
            "missing_prior_inputs_count": len(missing),
            "missing_prior_input_name_hashes": [stable_hash(name) for name in missing],
            "request_count": 0,
            "primary_blockers": PRIMARY_BLOCKERS,
            "acquisition_actions_requested": ACQUISITION_ACTIONS_REQUESTED,
            "executor_after_acquisition_allowed": False,
            "external_comparable_repair_credit_count": 0,
            "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
            "training_allowed": False,
            "admission_allowed": False,
            "packaging_allowed": False,
            "execution_performed_by_stage": False,
            "emitted_training_rows": 0,
            "sealed_eval_rows": 0,
            "public_raw_leak_guardrail": {
                "scan_passed": True,
                "raw_leak_count": 0,
                "policy": "hash_only_public_safe_no_raw_content",
            },
        }
        write_json(SUMMARY_OUT, summary)
        print(json.dumps(summary, sort_keys=True))
        return

    stage12463 = read_json(STAGE12463_SUMMARY)
    stage12462 = read_json(STAGE12462_SUMMARY)
    work_order_items = read_jsonl(STAGE12462_ITEMS)
    stage12333 = read_json(STAGE12333_SUMMARY)
    stage12336 = read_json(STAGE12336_AUDIT)
    stage12327_count = len(read_jsonl(STAGE12327_CANDIDATES))

    input_blockers = validate_inputs(stage12463, stage12462, work_order_items)
    decision = (
        "request_ready_no_execution_no_training"
        if not input_blockers
        else "blocked_missing_prior_work_order"
    )
    repair_items = build_work_items(work_order_items) if not input_blockers else []

    request = {
        "record_type": "stage12464_bears_source_acquisition_or_hydration_repair_request_v1",
        "stage": STAGE,
        "decision": decision,
        "claim_boundary": (
            "Request only. No network access, source checkout, submodule initialization, "
            "verifier execution, training, packaging, row admission, or sealed evaluation."
        ),
        "request_count": len(repair_items),
        "primary_blockers": PRIMARY_BLOCKERS,
        "blocker_counts": {blocker: len(repair_items) for blocker in PRIMARY_BLOCKERS},
        "required_missing_proof_slots": REQUIRED_MISSING_PROOF_SLOTS,
        "acquisition_actions_requested": ACQUISITION_ACTIONS_REQUESTED,
        "executor_after_acquisition_allowed": False,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "language_bucket": LANGUAGE_BUCKET,
        "public_raw_leak_guardrail": {
            "policy": "hash_only_public_safe_no_raw_repo_names_paths_urls_commands_outputs_diffs_or_source_text",
            "work_items_hash_only": True,
            "private_executor_may_join_raw_materials": True,
            "stage12464_emits_raw_materials": False,
        },
        "prior_stage_refs": {
            "stage12463_summary_hash": file_hash(STAGE12463_SUMMARY),
            "stage12462_summary_hash": file_hash(STAGE12462_SUMMARY),
            "stage12462_work_items_hash": file_hash(STAGE12462_ITEMS),
            "stage12333_summary_hash": file_hash(STAGE12333_SUMMARY),
            "stage12336_audit_hash": file_hash(STAGE12336_AUDIT),
            "stage12327_candidate_count": stage12327_count,
            "stage12327_candidates_hash": file_hash(STAGE12327_CANDIDATES),
        },
        "prior_evidence_status": {
            "stage12463_decision": stage12463.get("decision"),
            "stage12462_decision": stage12462.get("decision"),
            "stage12333_decision": stage12333.get("decision"),
            "stage12336_decision": stage12336.get("decision"),
            "stage12463_local_execution_feasible_now": stage12463.get(
                "local_execution_feasible_now"
            ),
        },
        "blocked_if_not_acquired": True,
        "work_item_count": len(repair_items),
        "work_item_ref_hashes": [row["request_item_ref_hash"] for row in repair_items],
    }

    public_issues = scan_public("request", request)
    public_issues.extend(scan_public("work_items", repair_items))
    raw_leak_count = len(public_issues)
    guardrail = {
        "scan_passed": raw_leak_count == 0,
        "raw_leak_count": raw_leak_count,
        "issue_ref_hashes": [stable_hash(issue) for issue in public_issues],
        "policy": "hash_only_public_safe_no_raw_content",
    }
    request["public_raw_leak_guardrail"].update(guardrail)

    summary = {
        "record_type": "stage12464_bears_source_acquisition_or_hydration_repair_request_summary_v1",
        "stage": STAGE,
        "decision": decision if guardrail["scan_passed"] else "blocked_missing_prior_work_order",
        "request_count": len(repair_items) if guardrail["scan_passed"] else 0,
        "primary_blockers": PRIMARY_BLOCKERS,
        "acquisition_actions_requested": ACQUISITION_ACTIONS_REQUESTED,
        "executor_after_acquisition_allowed": False,
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "public_raw_leak_guardrail": guardrail,
        "guardrail_scan_passed": guardrail["scan_passed"],
        "raw_leak_count": raw_leak_count,
        "schema_issue_count": 0,
        "next_stage_recommendation": "stage12465_bears_source_acquisition_hydration_repair_executor",
        "next_stage_execution_allowed_by_stage12464": False,
        "input_validation_blockers": input_blockers,
        "artifact_hashes": {
            "source_acquisition_or_hydration_repair_request": stable_hash(request),
            "bears_hydration_repair_work_items": stable_hash(repair_items),
        },
    }
    request["summary_mirror"] = {
        key: summary[key]
        for key in [
            "decision",
            "request_count",
            "primary_blockers",
            "acquisition_actions_requested",
            "executor_after_acquisition_allowed",
            "external_comparable_repair_credit_count",
            "remaining_external_fail_to_pass_gap",
            "training_allowed",
            "admission_allowed",
            "packaging_allowed",
            "execution_performed_by_stage",
            "emitted_training_rows",
            "sealed_eval_rows",
            "public_raw_leak_guardrail",
            "guardrail_scan_passed",
            "raw_leak_count",
            "schema_issue_count",
            "next_stage_recommendation",
            "next_stage_execution_allowed_by_stage12464",
        ]
    }

    write_json(REQUEST_OUT, request)
    write_jsonl(WORK_ITEMS_OUT, repair_items if guardrail["scan_passed"] else [])
    write_json(SUMMARY_OUT, summary)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
