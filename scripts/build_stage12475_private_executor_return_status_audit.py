#!/usr/bin/env python3
"""Fail-closed status audit for Stage12474 private executor requests.

Stage12475 checks whether private proof-slot returns exist for the Stage12474
request-only handoff. It emits pending/blocked accounting only. It does not
execute, hydrate, replay, use network, train, admit, package, or award repair
credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12475_private_executor_return_status_audit"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12474 = "stage12474_private_executor_request_contract"
STAGE12467 = "stage12467_non_bears_trace_transition_repair_proof_request_preflight"

STAGE12468_OUT = ROOT / "runs/local/artifacts" / STAGE12468
STAGE12474_OUT = ROOT / "runs/local/artifacts" / STAGE12474
RETURN_FILE = ROOT / "runs/local/artifacts" / STAGE12467 / "private_proof_slot_returns.jsonl"

STAGE12468_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12468}.json"
STAGE12474_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12474}.json"
VALIDATOR_CONTRACT_IN = STAGE12468_OUT / "validator_contract.json"
REQUEST_ITEMS_IN = STAGE12474_OUT / "private_executor_request_items_ref.jsonl"
EXCLUDED_ITEMS_IN = STAGE12474_OUT / "excluded_blocked_locator_work_items_ref.jsonl"

PENDING_OUT = OUT_DIR / "pending_private_executor_request_items_ref.jsonl"
RETURN_STATUS_OUT = OUT_DIR / "private_return_status_ref.jsonl"
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
    "emitted_training_rows": 0,
    "sealed_eval_rows": 0,
}
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
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file)",
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
            value["_stage12475_input_line_index"] = line_no
            rows.append(value)
    return rows, issues


def count_jsonl_if_exists(path: Path) -> tuple[int, Counter[str]]:
    if not path.exists():
        return 0, Counter({"private_return_file_missing": 1})
    count = 0
    issues: Counter[str] = Counter()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            count += 1
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                issues["private_return_jsonl_invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["private_return_jsonl_row_not_object"] += 1
    return count, issues


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


def pending_ref(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12475_pending_private_executor_request_item_ref_hash_only_v1",
        "request_item_ref_hash": row.get("request_item_ref_hash"),
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "proof_request_id_hash": row.get("proof_request_id_hash"),
        "lane_ref_hash": row.get("lane_ref_hash"),
        "language_family_label_hash": row.get("language_family_label_hash"),
        "pending_reason": "private_proof_slot_return_not_available_or_not_validator_complete",
        "next_required_stage": STAGE12468,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def main() -> int:
    request_items, request_issues = read_jsonl(REQUEST_ITEMS_IN)
    excluded_items, excluded_issues = read_jsonl(EXCLUDED_ITEMS_IN)
    stage12474_summary, summary74_issues = read_json(STAGE12474_SUMMARY)
    stage12468_summary, summary68_issues = read_json(STAGE12468_SUMMARY)
    validator_contract, contract_issues = read_json(VALIDATOR_CONTRACT_IN)
    private_return_row_count, return_issues = count_jsonl_if_exists(RETURN_FILE)

    stage_blockers: list[str] = []
    for prefix, issues in [
        ("stage12474_request_items", request_issues),
        ("stage12474_excluded_items", excluded_issues),
        ("stage12474_summary", summary74_issues),
        ("stage12468_summary", summary68_issues),
        ("stage12468_validator_contract", contract_issues),
    ]:
        stage_blockers.extend(f"{prefix}_{key}" for key in issues)

    if stage12474_summary.get("stage") != STAGE12474:
        stage_blockers.append("stage12474_summary_unexpected_stage")
    if stage12474_summary.get("guardrail_scan_passed") is not True:
        stage_blockers.append("stage12474_guardrail_not_passed")
    if stage12474_summary.get("raw_leak_count") != 0:
        stage_blockers.append("stage12474_raw_leak_count_not_zero")
    if stage12474_summary.get("schema_issue_count") != 0:
        stage_blockers.append("stage12474_schema_issue_count_not_zero")
    if stage12474_summary.get("private_executor_request_item_count") != len(request_items):
        stage_blockers.append("stage12474_request_item_count_mismatch")
    if stage12474_summary.get("excluded_blocked_locator_work_item_count") != len(excluded_items):
        stage_blockers.append("stage12474_excluded_item_count_mismatch")
    for key, expected in FALSE_GUARDS.items():
        if stage12474_summary.get(key) is not expected:
            stage_blockers.append(f"stage12474_{key}_not_false")
    for key, expected in ZERO_GUARDS.items():
        if stage12474_summary.get(key) != expected:
            stage_blockers.append(f"stage12474_{key}_not_{expected}")

    if validator_contract.get("stage") != STAGE12468:
        stage_blockers.append("stage12468_validator_contract_unexpected_stage")
    if validator_contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        stage_blockers.append("stage12468_status_family_mismatch")

    pending_items = [pending_ref(row) for row in request_items]
    return_status_rows = [{
        "record_type": "stage12475_private_return_status_ref_hash_only_v1",
        "private_return_target_ref": "stage12468_contract_optional_private_return_jsonl_ref",
        "private_return_file_exists": RETURN_FILE.exists(),
        "proof_slot_return_file_exists": RETURN_FILE.exists(),
        "private_return_file_ref_hash": file_hash(RETURN_FILE),
        "private_return_row_count": private_return_row_count,
        "private_return_issue_counts": dict(sorted(return_issues.items())),
        "stage12468_current_decision_ref_hash": stable_hash(stage12468_summary.get("decision")),
        "stage12468_current_proof_complete_count": stage12468_summary.get("proof_complete_count", 0),
        "stage12468_current_external_credit_count": stage12468_summary.get("external_comparable_repair_credit_count", 0),
        "rerun_stage12468_required": True,
        "stage12468_rerun_reason": (
            "missing_private_return" if not RETURN_FILE.exists()
            else "private_return_present_requires_validation"
        ),
        "proof_returns_pending": len(pending_items),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }]

    pending_count = len(pending_items)
    current_validator_credit = stage12468_summary.get("external_comparable_repair_credit_count", 0)
    summary = {
        "stage": STAGE,
        "record_type": "stage12475_private_executor_return_status_audit_summary_v1",
        "decision": (
            "private_executor_returns_present_rerun_stage12468_required_zero_credit_by_this_stage"
            if RETURN_FILE.exists() and not stage_blockers
            else "fail_closed_missing_private_executor_returns_zero_credit"
        ),
        "control_boundary": (
            "Status audit only. Stage12475 does not inspect raw private locator content, "
            "execute, hydrate, replay, use network, train, admit, package, or award repair credit."
        ),
        "source_stage_refs": [STAGE12474, STAGE12468],
        "private_executor_request_item_count": len(request_items),
        "excluded_blocked_locator_work_item_count": len(excluded_items),
        "pending_private_executor_request_item_count": pending_count,
        "private_return_file_exists": RETURN_FILE.exists(),
        "proof_slot_return_file_exists": RETURN_FILE.exists(),
        "private_return_file_ref_hash": file_hash(RETURN_FILE),
        "private_return_row_count": private_return_row_count,
        "private_return_issue_counts": dict(sorted(return_issues.items())),
        "rerun_stage12468_required": True,
        "stage12468_rerun_required": True,
        "stage12468_rerun_reason": (
            "missing_private_return" if not RETURN_FILE.exists()
            else "private_return_present_requires_validation"
        ),
        "accepted_stage12474_request_refs_pending_count": pending_count,
        "return_fabricated": False,
        "safe_to_continue": False,
        "audit_complete": True,
        "stage12468_current_decision_ref_hash": stable_hash(stage12468_summary.get("decision")),
        "stage12468_current_proof_complete_count": stage12468_summary.get("proof_complete_count", 0),
        "stage12468_current_external_comparable_repair_credit_count": current_validator_credit,
        "external_comparable_repair_credit_count": 0,
        "credited_by_this_stage": False,
        "credit_authority_stage": STAGE12468,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "blocked_language_counts": stage12474_summary.get("blocked_language_counts") or {},
        "c_cpp_locator_gap": stage12474_summary.get("c_cpp_locator_gap", 0),
        "next_required_actions": [
            "private_executor_populate_stage12468_contract_return_file_for_stage12474_request_refs",
            "rerun_stage12468_validator_after_returns_exist",
            "only_stage12468_validator_complete_returns_may_count_external_repair_credit",
            "recover_c_cpp_locator_refs_separately_without_weakening_locator_requirements",
        ],
        "stage_blockers": sorted(set(stage_blockers)),
        **FALSE_GUARDS,
        "packaging_allowed": False,
        "emitted_training_rows": 0,
        "sealed_eval_rows": 0,
        "artifact_refs": {
            "pending_private_executor_request_items_ref": "stage12475_pending_private_executor_request_items_ref_jsonl",
            "private_return_status_ref": "stage12475_private_return_status_ref_jsonl",
            "guardrail_scan": "stage12475_guardrail_scan_json",
            "local_summary": "stage12475_local_summary_json",
            "summary": "stage12475_summary_json",
        },
        "input_artifact_hashes": {
            "stage12474_private_executor_request_items_ref": file_hash(REQUEST_ITEMS_IN),
            "stage12474_excluded_blocked_locator_work_items_ref": file_hash(EXCLUDED_ITEMS_IN),
            "stage12474_summary": file_hash(STAGE12474_SUMMARY),
            "stage12468_summary": file_hash(STAGE12468_SUMMARY),
            "stage12468_validator_contract": file_hash(VALIDATOR_CONTRACT_IN),
        },
    }

    public_payload = {
        "pending_private_executor_request_items_ref": pending_items,
        "private_return_status_ref": return_status_rows,
        "summary": summary,
    }
    scan_issues = public_scan("stage12475_public_artifacts", public_payload)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12475_guardrail_scan_v1",
        "scan_scope": "stage12475_public_summary_and_hash_only_status_indexes",
        "scan_status": "completed",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "policy": "no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }

    if scan_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        summary["stage_blockers"] = sorted(set([*summary["stage_blockers"], "stage12475_public_guardrail_scan_failed"]))
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "pending_private_executor_request_item_count": pending_count,
        "private_return_file_exists": RETURN_FILE.exists(),
        "private_return_row_count": private_return_row_count,
        "stage_blockers": summary["stage_blockers"],
        "raw_leak_count": summary["raw_leak_count"],
    })
    summary["artifact_hashes"] = {
        "pending_private_executor_request_items_ref": stable_hash(pending_items),
        "private_return_status_ref": stable_hash(return_status_rows),
        "guardrail_scan": stable_hash(guardrail_scan),
    }

    write_jsonl(PENDING_OUT, pending_items)
    write_jsonl(RETURN_STATUS_OUT, return_status_rows)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "private_executor_request_item_count": len(request_items),
        "pending_private_executor_request_item_count": pending_count,
        "private_return_file_exists": RETURN_FILE.exists(),
        "private_return_row_count": private_return_row_count,
        "rerun_stage12468_required": summary["rerun_stage12468_required"],
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "c_cpp_locator_gap": summary["c_cpp_locator_gap"],
        "guardrail_scan_passed": summary["guardrail_scan_passed"],
        "raw_leak_count": summary["raw_leak_count"],
        "schema_issue_count": summary["schema_issue_count"],
        "training_allowed": False,
        "admission_allowed": False,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
