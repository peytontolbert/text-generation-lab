#!/usr/bin/env python3
"""Request-only private executor handoff for Stage12473 accepted refs.

Stage12474 emits hash-only executor request items for the accepted locator refs.
It does not read private locators, execute commands, hydrate repos, replay traces,
train, admit rows, or award repair credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12474_private_executor_request_contract"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12473 = "stage12473_locator_augmented_work_order_preflight"

STAGE12468_OUT = ROOT / "runs/local/artifacts" / STAGE12468
STAGE12473_OUT = ROOT / "runs/local/artifacts" / STAGE12473

VALIDATOR_CONTRACT_IN = STAGE12468_OUT / "validator_contract.json"
STAGE12473_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12473}.json"
STAGE12473_ACCEPTED_IN = STAGE12473_OUT / "accepted_locator_work_items_ref.jsonl"
STAGE12473_BLOCKED_IN = STAGE12473_OUT / "blocked_locator_work_items_ref.jsonl"

REQUEST_OUT = OUT_DIR / "private_executor_request_items_ref.jsonl"
EXCLUDED_OUT = OUT_DIR / "excluded_blocked_locator_work_items_ref.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
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
    "external_comparable_repair_credit_count": 0,
    "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}
REQUIRED_FALSE_RETURN_FLAGS = {
    "training_after_return_allowed": False,
    "admission_after_return_allowed": False,
    "packaging_after_return_allowed": False,
    "external_repair_credit_after_return_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
}
REQUIRED_EXPLICIT_PRESENT_SLOTS = [
    "before_verifier_status_fail",
    "before_status_fail",
    "after_or_before_plus_patch_verifier_status_pass",
    "after_or_before_plus_patch_status_pass",
    "anti_leak_public_rendering_pass",
    "protected_overlap_audit_pass",
]
FORBIDDEN_PUBLIC_KEYS = {
    "body", "cmd", "command", "commands", "commit", "commit_sha", "content",
    "diff", "file_content", "file_path", "patch", "patch_body", "path",
    "paths", "raw", "raw_content", "raw_text", "repo", "repo_id",
    "repo_name", "repository", "sha", "source", "source_text", "stderr",
    "stdout", "text", "uri", "uris", "url", "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label|input|excluded|request|contract)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\\.|diff --git|@@ |^\\+\\+\\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\\b(?:git clone|git apply|pytest\\s|python -c|bash -|sh -|curl\\s|"
    r"stdout|stderr|traceback|terminal output|command output)\\b|"
    r"\\b[0-9a-f]{40}\\b|"
    r"\\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\\b",
    re.IGNORECASE | re.MULTILINE,
)


def stable_hash(value: Any, n: int = 24) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(f"{STAGE}:{payload}".encode("utf-8")).hexdigest()[:n]


def file_hash(path: Path, n: int = 24) -> str:
    if not path.exists() or not path.is_file():
        return "missing"
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:n]


def read_json(path: Path) -> tuple[dict[str, Any], Counter[str]]:
    issues: Counter[str] = Counter()
    if not path.exists():
        issues[f"{path.name}_missing"] += 1
        return {}, issues
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        issues[f"{path.name}_invalid_json"] += 1
        return {}, issues
    if not isinstance(value, dict):
        issues[f"{path.name}_not_object"] += 1
        return {}, issues
    return value, issues


def read_jsonl(path: Path) -> tuple[list[dict[str, Any]], Counter[str]]:
    rows: list[dict[str, Any]] = []
    issues: Counter[str] = Counter()
    if not path.exists():
        issues[f"{path.name}_missing"] += 1
        return rows, issues
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["input_jsonl_invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["input_jsonl_row_not_object"] += 1
                continue
            value["_stage12474_input_line_index"] = line_no
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, sort_keys=True) + "\n")


def public_scan(label: str, value: Any) -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(f"{label}.{key}", child))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(f"{label}[{index}]", child))
    return issues


def make_request_item(row: dict[str, Any], validator_contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12474_private_executor_request_item_ref_hash_only_v1",
        "request_item_ref_hash": stable_hash({
            "stage12473_work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
            "stage12473_proof_request_ref_hash": row.get("proof_request_ref_hash"),
            "stage12473_locator_bundle_ref_hash": row.get("locator_bundle_ref_hash"),
        }),
        "source_accepted_record_type_hash": stable_hash(row.get("record_type")),
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "proof_request_id_hash": row.get("proof_request_id_hash"),
        "lane_ref_hash": row.get("lane_ref_hash"),
        "language_family_label_hash": row.get("language_family_label_hash"),
        "locator_bundle_ref_hash": row.get("locator_bundle_ref_hash"),
        "required_return_fields_ref_hash": row.get("required_return_fields_ref_hash"),
        "required_combined_slots_ref_hash": row.get("required_combined_slots_ref_hash"),
        "validator_contract_ref_hash": row.get("validator_contract_ref_hash"),
        "expected_validator_return_target_ref": "stage12468_contract_optional_private_return_jsonl_ref",
        "return_must_be_validator_compatible_with_stage": STAGE12468,
        "required_return_field_count": len(validator_contract.get("required_return_fields") or []),
        "required_proof_slot_count": len(validator_contract.get("required_proof_slots") or []),
        "required_explicit_present_slots_ref_hash": stable_hash(REQUIRED_EXPLICIT_PRESENT_SLOTS),
        "requested_status_family": EXPECTED_STATUS_FAMILY,
        "executor_payload_policy": "private_executor_may_use_private_locator_sidecar_public_return_hashes_only",
        "blocked_rows_excluded_from_executor_request": True,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        **REQUIRED_FALSE_RETURN_FLAGS,
    }


def make_excluded_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12474_excluded_blocked_locator_work_item_ref_hash_only_v1",
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "proof_request_id_hash": row.get("proof_request_id_hash"),
        "lane_ref_hash": row.get("lane_ref_hash"),
        "reason_hashes": row.get("reason_hashes") if isinstance(row.get("reason_hashes"), list) else [],
        "excluded_from_executor_request": True,
        "exclusion_reason_ref": "stage12473_blocked_locator_work_item_preflight_failed",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def main() -> int:
    accepted, accepted_issues = read_jsonl(STAGE12473_ACCEPTED_IN)
    blocked, blocked_issues = read_jsonl(STAGE12473_BLOCKED_IN)
    stage12473_summary, summary_issues = read_json(STAGE12473_SUMMARY)
    validator_contract, contract_issues = read_json(VALIDATOR_CONTRACT_IN)

    stage_blockers: list[str] = []
    for prefix, issues in [
        ("stage12473_accepted", accepted_issues),
        ("stage12473_blocked", blocked_issues),
        ("stage12473_summary", summary_issues),
        ("stage12468_validator_contract", contract_issues),
    ]:
        stage_blockers.extend(f"{prefix}_{key}" for key in issues)

    if stage12473_summary.get("stage") != STAGE12473:
        stage_blockers.append("stage12473_summary_unexpected_stage")
    if stage12473_summary.get("guardrail_scan_passed") is not True:
        stage_blockers.append("stage12473_guardrail_not_passed")
    if stage12473_summary.get("raw_leak_count") != 0:
        stage_blockers.append("stage12473_raw_leak_count_not_zero")
    if stage12473_summary.get("schema_issue_count") != 0:
        stage_blockers.append("stage12473_schema_issue_count_not_zero")
    if stage12473_summary.get("accepted_locator_work_item_count") != len(accepted):
        stage_blockers.append("stage12473_accepted_count_mismatch")
    if stage12473_summary.get("blocked_locator_work_item_count") != len(blocked):
        stage_blockers.append("stage12473_blocked_count_mismatch")
    if stage12473_summary.get("executor_request_allowed_count") != len(accepted):
        stage_blockers.append("stage12473_executor_allowed_count_mismatch")
    if stage12473_summary.get("executor_request_must_exclude_blocked_count") != len(blocked):
        stage_blockers.append("stage12473_executor_exclude_count_mismatch")
    for key, expected in FALSE_GUARDS.items():
        if stage12473_summary.get(key) is not expected:
            stage_blockers.append(f"stage12473_{key}_not_false")
    for key, expected in ZERO_GUARDS.items():
        if stage12473_summary.get(key) != expected:
            stage_blockers.append(f"stage12473_{key}_not_{expected}")

    if validator_contract.get("stage") != STAGE12468:
        stage_blockers.append("stage12468_validator_contract_unexpected_stage")
    if validator_contract.get("record_type") != "stage12468_private_return_validator_contract_v1":
        stage_blockers.append("stage12468_validator_contract_unexpected_record_type")
    if validator_contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        stage_blockers.append("stage12468_status_family_mismatch")
    if not accepted:
        stage_blockers.append("no_accepted_locator_refs_for_executor_request")

    stage_blockers = sorted(set(stage_blockers))
    request_items = [] if stage_blockers else [make_request_item(row, validator_contract) for row in accepted]
    excluded_items = [make_excluded_ref(row) for row in blocked]

    summary = {
        "stage": STAGE,
        "record_type": "stage12474_private_executor_request_contract_summary_v1",
        "decision": (
            "private_executor_request_ready_for_accepted_subset_zero_credit_no_execution"
            if request_items and not stage_blockers
            else "blocked_private_executor_request_contract_zero_credit"
        ),
        "control_boundary": (
            "Request-only public-safe executor handoff. This stage does not execute, "
            "hydrate, replay, use network, train, admit, package, or award repair credit."
        ),
        "source_stage_refs": [STAGE12473, STAGE12468],
        "stage12473_total_source_work_item_count": stage12473_summary.get("total_source_work_item_count"),
        "stage12473_input_locator_augmented_work_item_count": stage12473_summary.get("input_locator_augmented_work_item_count"),
        "accepted_locator_work_item_count": len(accepted),
        "private_executor_request_item_count": len(request_items),
        "blocked_locator_work_item_count": len(blocked),
        "excluded_blocked_locator_work_item_count": len(excluded_items),
        "executor_request_allowed_count": len(request_items),
        "executor_request_must_exclude_blocked_count": len(excluded_items),
        "accepted_language_counts": stage12473_summary.get("accepted_language_counts") or {},
        "blocked_language_counts": stage12473_summary.get("blocked_language_counts") or {},
        "c_cpp_locator_gap": stage12473_summary.get("c_cpp_locator_gap", 0),
        "expected_validator_return_target_ref": "stage12468_contract_optional_private_return_jsonl_ref",
        "return_must_be_validator_compatible_with_stage": STAGE12468,
        "required_return_fields": validator_contract.get("required_return_fields") or [],
        "allowed_return_top_level_keys": validator_contract.get("allowed_return_top_level_keys") or [],
        "required_proof_slots": validator_contract.get("required_proof_slots") or [],
        "required_explicit_present_slots": REQUIRED_EXPLICIT_PRESENT_SLOTS,
        "required_false_return_flags": REQUIRED_FALSE_RETURN_FLAGS,
        "request_policy": [
            "private_executor_may_use_private_locator_sidecar",
            "public_returns_must_be_stage12468_validator_compatible",
            "blocked_locator_refs_excluded_from_executor_payload",
            "no_raw_public_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
            "no_credit_until_stage12468_proof_complete_accepts_returns",
        ],
        "stage_blockers": stage_blockers,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "artifact_refs": {
            "private_executor_request_items_ref": "stage12474_private_executor_request_items_ref_jsonl",
            "excluded_blocked_locator_work_items_ref": "stage12474_excluded_blocked_locator_work_items_ref_jsonl",
            "guardrail_scan": "stage12474_guardrail_scan_json",
            "local_summary": "stage12474_local_summary_json",
            "summary": "stage12474_summary_json",
        },
        "input_artifact_hashes": {
            "stage12473_accepted_locator_work_items_ref": file_hash(STAGE12473_ACCEPTED_IN),
            "stage12473_blocked_locator_work_items_ref": file_hash(STAGE12473_BLOCKED_IN),
            "stage12473_summary": file_hash(STAGE12473_SUMMARY),
            "stage12468_validator_contract": file_hash(VALIDATOR_CONTRACT_IN),
        },
    }

    public_payload = {
        "private_executor_request_items_ref": request_items,
        "excluded_blocked_locator_work_items_ref": excluded_items,
        "summary": summary,
    }
    scan_issues = public_scan("stage12474_public_artifacts", public_payload)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12474_guardrail_scan_v1",
        "scan_scope": "stage12474_public_summary_and_hash_only_request_indexes",
        "scan_status": "completed",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "policy": "no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    if scan_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        summary["stage_blockers"] = sorted(set([*summary["stage_blockers"], "stage12474_public_guardrail_scan_failed"]))
        request_items = []
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["artifact_hashes"] = {
        "private_executor_request_items_ref": stable_hash(request_items),
        "excluded_blocked_locator_work_items_ref": stable_hash(excluded_items),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "private_executor_request_item_count": len(request_items),
        "excluded_blocked_locator_work_item_count": len(excluded_items),
        "stage_blockers": summary["stage_blockers"],
        "raw_leak_count": summary["raw_leak_count"],
    })

    write_jsonl(REQUEST_OUT, request_items)
    write_jsonl(EXCLUDED_OUT, excluded_items)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "private_executor_request_item_count": len(request_items),
        "excluded_blocked_locator_work_item_count": len(excluded_items),
        "c_cpp_locator_gap": summary["c_cpp_locator_gap"],
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "guardrail_scan_passed": summary["guardrail_scan_passed"],
        "raw_leak_count": summary["raw_leak_count"],
        "schema_issue_count": summary["schema_issue_count"],
        "training_allowed": False,
        "admission_allowed": False,
        "execution_performed_by_stage": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
