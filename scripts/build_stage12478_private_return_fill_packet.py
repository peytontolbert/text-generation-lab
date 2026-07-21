#!/usr/bin/env python3
"""Public-safe private-return fill packet for Stage12474 accepted refs."""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12478_private_return_fill_packet"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12474 = "stage12474_private_executor_request_contract"
STAGE12475 = "stage12475_private_executor_return_status_audit"

STAGE12468_OUT = ROOT / "runs/local/artifacts" / STAGE12468
STAGE12474_OUT = ROOT / "runs/local/artifacts" / STAGE12474

VALIDATOR_CONTRACT_IN = STAGE12468_OUT / "validator_contract.json"
STAGE12474_REQUESTS_IN = STAGE12474_OUT / "private_executor_request_items_ref.jsonl"
STAGE12474_EXCLUDED_IN = STAGE12474_OUT / "excluded_blocked_locator_work_items_ref.jsonl"
STAGE12474_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12474}.json"
STAGE12475_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12475}.json"

FILL_PACKET_OUT = OUT_DIR / "private_return_fill_packet_items_ref.jsonl"
RETURN_TEMPLATE_OUT = OUT_DIR / "stage12468_return_row_template.json"
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
REQUIRED_FALSE_RETURN_FLAGS = {
    "training_after_return_allowed": False,
    "admission_after_return_allowed": False,
    "packaging_after_return_allowed": False,
    "external_repair_credit_after_return_allowed": False,
    "execution_performed_by_stage": False,
    "hydration_performed_by_stage": False,
    "replay_performed_by_stage": False,
}
EXPLICIT_PRESENT_SLOTS = [
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
    r"locator|candidate|context|label|input|excluded|request|contract|pending|file|"
    r"packet|template|placeholder|fill|gate|credit|authority)",
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
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()[:n]


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
    with path.open(encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
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
            value["_stage12478_input_line_index"] = line_no
            rows.append(value)
    return rows, issues


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, sort_keys=True) + "\n")


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


def template_from_contract(contract: dict[str, Any]) -> dict[str, Any]:
    slots = contract.get("required_proof_slots") if isinstance(contract.get("required_proof_slots"), list) else []
    return {
        "record_type": "stage12478_stage12468_return_row_template_v1",
        "template_is_public_safe_placeholders_only": True,
        "target_validator_stage": STAGE12468,
        "approved_top_level_keys": contract.get("allowed_return_top_level_keys") or [],
        "required_return_fields": contract.get("required_return_fields") or [],
        "requested_status_family_literal": EXPECTED_STATUS_FAMILY,
        "valid_language_labels": contract.get("valid_language_labels") or [],
        "slot_statuses_required_shape": {slot: "present" for slot in slots},
        "slot_hashes_required_shape": {slot: "private_evidence_hash_required" for slot in slots},
        "explicit_present_slots": EXPLICIT_PRESENT_SLOTS,
        "proof_complete_required_literal": True,
        "anti_leak_pass_required_literal": True,
        "blocker_codes_required_empty_or_absent": True,
        "required_false_return_flags": REQUIRED_FALSE_RETURN_FLAGS,
        "hash_format_policy": "24_32_40_64_hex_or_sha256_colon_64hex_non_placeholder",
        "placeholder_hash_values_rejected": [
            "claim", "claimed", "equivalent", "missing", "none", "ok", "pass",
            "passed", "placeholder", "present", "proven", "redacted", "todo",
            "true", "unknown", "yes",
        ],
        "public_safety_policy": "no_raw_locator_repo_path_command_sha_url_diff_source_stdout_stderr",
    }


def fill_packet_item(row: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_type": "stage12478_private_return_fill_packet_item_ref_hash_only_v1",
        "fill_packet_item_ref_hash": stable_hash({
            "request_item_ref_hash": row.get("request_item_ref_hash"),
            "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        }),
        "request_item_ref_hash": row.get("request_item_ref_hash"),
        "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": row.get("proof_request_ref_hash"),
        "proof_request_id_hash": row.get("proof_request_id_hash"),
        "lane_ref_hash": row.get("lane_ref_hash"),
        "language_family_label_hash": row.get("language_family_label_hash"),
        "locator_bundle_ref_hash": row.get("locator_bundle_ref_hash"),
        "target_validator_stage": STAGE12468,
        "return_target_ref": "stage12468_contract_optional_private_return_jsonl_ref",
        "required_return_fields_ref_hash": stable_hash(contract.get("required_return_fields") or []),
        "required_proof_slots_ref_hash": stable_hash(contract.get("required_proof_slots") or []),
        "required_explicit_present_slots_ref_hash": stable_hash(EXPLICIT_PRESENT_SLOTS),
        "return_row_template_ref_hash": stable_hash(template_from_contract(contract)),
        "private_executor_must_fill_real_private_evidence_hashes": True,
        "public_packet_contains_no_private_evidence": True,
        "locator_is_proof": False,
        "proof_credit_authority_stage": STAGE12468,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
    }


def main() -> int:
    request_rows, request_issues = read_jsonl(STAGE12474_REQUESTS_IN)
    excluded_rows, excluded_issues = read_jsonl(STAGE12474_EXCLUDED_IN)
    stage12474_summary, summary74_issues = read_json(STAGE12474_SUMMARY)
    stage12475_summary, summary75_issues = read_json(STAGE12475_SUMMARY)
    contract, contract_issues = read_json(VALIDATOR_CONTRACT_IN)

    blockers: list[str] = []
    for prefix, issues in [
        ("stage12474_requests", request_issues),
        ("stage12474_excluded", excluded_issues),
        ("stage12474_summary", summary74_issues),
        ("stage12475_summary", summary75_issues),
        ("stage12468_contract", contract_issues),
    ]:
        blockers.extend(f"{prefix}_{key}" for key in issues)
    if stage12474_summary.get("private_executor_request_item_count") != len(request_rows):
        blockers.append("stage12474_request_item_count_mismatch")
    if stage12474_summary.get("excluded_blocked_locator_work_item_count") != len(excluded_rows):
        blockers.append("stage12474_excluded_count_mismatch")
    if stage12475_summary.get("pending_private_executor_request_item_count") != len(request_rows):
        blockers.append("stage12475_pending_count_mismatch")
    if stage12475_summary.get("private_return_file_exists") is not False:
        blockers.append("stage12475_private_return_already_exists_unexpected_for_fill_packet")
    if contract.get("stage") != STAGE12468:
        blockers.append("stage12468_contract_unexpected_stage")
    if contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        blockers.append("stage12468_contract_status_family_mismatch")
    for key, expected in FALSE_GUARDS.items():
        if stage12474_summary.get(key) is not expected:
            blockers.append(f"stage12474_{key}_not_false")
        if stage12475_summary.get(key) is not expected:
            blockers.append(f"stage12475_{key}_not_false")

    template = template_from_contract(contract)
    fill_rows = [] if blockers else [fill_packet_item(row, contract) for row in request_rows]

    summary = {
        "stage": STAGE,
        "record_type": "stage12478_private_return_fill_packet_summary_v1",
        "decision": "private_return_fill_packet_ready_zero_credit_no_execution" if fill_rows and not blockers else "blocked_private_return_fill_packet_zero_credit",
        "claim_boundary": "Public-safe fill packet only. It does not execute, hydrate, replay, train, admit, package, or award proof credit.",
        "source_stage_refs": [STAGE12474, STAGE12475, STAGE12468],
        "accepted_stage12474_request_refs_pending": len(request_rows),
        "fill_packet_item_count": len(fill_rows),
        "blocked_refs_excluded_count": len(excluded_rows),
        "return_template_ref_hash": stable_hash(template),
        "target_validator_stage": STAGE12468,
        "proof_credit_authority_stage": STAGE12468,
        "required_return_fields": contract.get("required_return_fields") or [],
        "required_proof_slot_count": len(contract.get("required_proof_slots") or []),
        "required_explicit_present_slots": EXPLICIT_PRESENT_SLOTS,
        "required_false_return_flags": REQUIRED_FALSE_RETURN_FLAGS,
        "stage_blockers": sorted(set(blockers)),
        "hard_reject_rules": [
            "reject_raw_locator_repo_path_command_sha_url_diff_source_stdout_stderr",
            "reject_placeholder_or_claim_hash_values",
            "reject_missing_before_fail_or_after_patch_pass_slots",
            "reject_pass_to_pass_as_fail_to_pass_repair",
            "reject_metadata_only_or_co_presence_as_causality",
            "reject_duplicate_request_or_lane_mismatch",
            "reject_unapproved_top_level_keys_or_extra_slot_keys",
        ],
        "next_required_actions": [
            "private_executor_fill_stage12468_compatible_return_rows_from_real_private_evidence",
            "rerun_stage12468_validator",
            "only_stage12468_validator_complete_returns_may_count_credit",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "artifact_refs": {
            "private_return_fill_packet_items_ref": "stage12478_private_return_fill_packet_items_ref_jsonl",
            "stage12468_return_row_template": "stage12478_stage12468_return_row_template_json",
            "guardrail_scan": "stage12478_guardrail_scan_json",
            "local_summary": "stage12478_local_summary_json",
            "summary": "stage12478_summary_json",
        },
        "input_artifact_hashes": {
            "stage12474_request_items": file_hash(STAGE12474_REQUESTS_IN),
            "stage12474_excluded_items": file_hash(STAGE12474_EXCLUDED_IN),
            "stage12474_summary": file_hash(STAGE12474_SUMMARY),
            "stage12475_summary": file_hash(STAGE12475_SUMMARY),
            "stage12468_validator_contract": file_hash(VALIDATOR_CONTRACT_IN),
        },
    }

    public_payload = {"summary": summary, "fill_packet_items": fill_rows, "return_template": template}
    scan_issues = public_scan("stage12478_public_artifacts", public_payload)
    guardrail = {
        "stage": STAGE,
        "record_type": "stage12478_guardrail_scan_v1",
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
        summary["stage_blockers"] = sorted(set([*summary["stage_blockers"], "stage12478_public_guardrail_scan_failed"]))
        fill_rows = []
    summary["guardrail_scan_passed"] = guardrail["scan_passed"]
    summary["raw_leak_count"] = guardrail["raw_leak_count"]
    summary["schema_issue_count"] = len(summary["stage_blockers"])
    summary["summary_hash"] = stable_hash({
        "decision": summary["decision"],
        "fill_packet_item_count": len(fill_rows),
        "raw_leak_count": summary["raw_leak_count"],
        "stage_blockers": summary["stage_blockers"],
    })

    write_jsonl(FILL_PACKET_OUT, fill_rows)
    write_json(RETURN_TEMPLATE_OUT, template)
    write_json(GUARDRAIL_OUT, guardrail)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(json.dumps({
        "stage": STAGE,
        "decision": summary["decision"],
        "fill_packet_item_count": len(fill_rows),
        "accepted_stage12474_request_refs_pending": len(request_rows),
        "blocked_refs_excluded_count": len(excluded_rows),
        "external_comparable_repair_credit_count": 0,
        "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
        "guardrail_scan_passed": summary["guardrail_scan_passed"],
        "raw_leak_count": summary["raw_leak_count"],
        "schema_issue_count": summary["schema_issue_count"],
        "training_allowed": False,
        "admission_allowed": False,
    }, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
