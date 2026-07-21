#!/usr/bin/env python3
"""Fail-closed preflight for Stage12472 locator-augmented work items.

Stage12473 validates that locator-augmented work-order rows are actionable
against the Stage12470 locator requirements and Stage12468 private return
contract. It emits hash-only references. It does not execute, hydrate, replay,
use network, train, admit, or package anything.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12473_locator_augmented_work_order_preflight"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"
STAGE12470 = "stage12470_non_bears_private_return_locator_preflight"
STAGE12472 = "stage12472_locator_augmented_non_bears_work_order"

STAGE12468_OUT = ROOT / "runs/local/artifacts" / STAGE12468
STAGE12470_OUT = ROOT / "runs/local/artifacts" / STAGE12470
STAGE12472_OUT = ROOT / "runs/local/artifacts" / STAGE12472

VALIDATOR_CONTRACT_IN = STAGE12468_OUT / "validator_contract.json"
STAGE12470_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12470}.json"
STAGE12472_AUGMENTED_IN = STAGE12472_OUT / "locator_augmented_work_items.jsonl"
STAGE12472_BLOCKED_IN = STAGE12472_OUT / "blocked_locator_augmented_requests.jsonl"
STAGE12472_SUMMARY = ROOT / "runs/summaries" / f"{STAGE12472}.json"

ACCEPTED_OUT = OUT_DIR / "accepted_locator_work_items_ref.jsonl"
BLOCKED_OUT = OUT_DIR / "blocked_locator_work_items_ref.jsonl"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_GAP = 15
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
EXPECTED_CONTRACT_RETURN_INPUT = (
    "runs/local/artifacts/"
    "stage12467_non_bears_trace_transition_repair_proof_request_preflight/"
    "private_proof_slot_returns.jsonl"
)
REQUIRED_EXPLICIT_PRESENT_SLOTS = [
    "before_verifier_status_fail",
    "before_status_fail",
    "after_or_before_plus_patch_verifier_status_pass",
    "after_or_before_plus_patch_status_pass",
    "anti_leak_public_rendering_pass",
    "protected_overlap_audit_pass",
]
DEFAULT_REQUIRED_LOCATOR_FIELDS = [
    "source_adapter_candidate_ref_hash",
    "private_locator_ref_hash",
    "source_root_label_hash",
    "lane_candidate_family_hash",
    "private_execution_context_ref_hash",
]
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

FORBIDDEN_PUBLIC_KEYS = {
    "body",
    "cmd",
    "command",
    "commands",
    "commit",
    "commit_sha",
    "content",
    "diff",
    "file_content",
    "file_path",
    "patch",
    "patch_body",
    "path",
    "paths",
    "raw",
    "raw_content",
    "raw_text",
    "repo",
    "repo_id",
    "repo_name",
    "repository",
    "sha",
    "source",
    "source_text",
    "stderr",
    "stdout",
    "text",
    "uri",
    "uris",
    "url",
    "urls",
}
PUBLIC_SAFE_KEY_RE = re.compile(
    r"(hash|hashes|ref|refs|id|ids|stage|schema|slot|slots|status|family|"
    r"lane|guardrail|issue|reason|count|policy|allowed|proof|return|artifact|"
    r"locator|candidate|context|label|input)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b|"
    r"\b[0-9a-f]{40}\b|"
    r"\b(?:Open-SWE|RepairThemAll|SakanaAI|SWE-Hero|SWE-Zero)\b",
    re.IGNORECASE | re.MULTILINE,
)
HASH_RE = re.compile(
    r"^(?:[0-9a-f]{24}|[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}|"
    r"sha256:[0-9a-f]{64})$",
    re.IGNORECASE,
)
PLACEHOLDER_VALUES = {
    "",
    "blocked",
    "claim",
    "claimed",
    "claimed_only",
    "equivalent",
    "fail",
    "false",
    "missing",
    "n_a",
    "na",
    "no",
    "none",
    "not_applicable",
    "null",
    "ok",
    "pass",
    "passed",
    "placeholder",
    "present",
    "proven",
    "redacted",
    "tbd",
    "todo",
    "true",
    "unknown",
    "yes",
}


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
            value["_stage12473_input_line_index"] = line_no
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


def unique_ordered(values: list[Any]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if isinstance(value, str) and value and value not in seen:
            seen.add(value)
            out.append(value)
    return out


def normalized(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value or "").strip().lower().replace("-", "_").replace("/", "_")


def valid_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    if normalized(value) in PLACEHOLDER_VALUES:
        return False
    if not HASH_RE.fullmatch(value.strip()):
        return False
    compact = re.sub(r"[^A-Za-z0-9]", "", value.strip())
    return bool(compact) and len(set(compact.lower())) > 1


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


def count_bucket(count: int) -> str:
    if count <= 0:
        return "0"
    if count == 1:
        return "1"
    if count <= 4:
        return "2-4"
    if count <= 9:
        return "5-9"
    if count <= 24:
        return "10-24"
    return "25-plus"


def required_locator_fields(stage12470_summary: dict[str, Any]) -> list[str]:
    fields = stage12470_summary.get("required_candidate_locator_fields")
    if not isinstance(fields, list) or not fields:
        return DEFAULT_REQUIRED_LOCATOR_FIELDS
    return unique_ordered(fields)


def required_combined_slots(
    item: dict[str, Any],
    validator_contract: dict[str, Any],
) -> list[str]:
    common = validator_contract.get("required_proof_slots")
    lane_slots_by_ref = validator_contract.get("lane_specific_required_proof_slots")
    lane_slots: list[str] = []
    if isinstance(lane_slots_by_ref, dict):
        lane_raw = lane_slots_by_ref.get(item.get("lane_ref"))
        if isinstance(lane_raw, list):
            lane_slots = unique_ordered(lane_raw)
    return unique_ordered([*(common if isinstance(common, list) else []), *lane_slots])


def subset_missing(required: list[str], actual: Any) -> list[str]:
    if not isinstance(actual, list):
        return required
    actual_set = {value for value in actual if isinstance(value, str)}
    return [value for value in required if value not in actual_set]


def input_blockers(
    item_issues: Counter[str],
    contract_issues: Counter[str],
    stage12470_issues: Counter[str],
    stage12472_issues: Counter[str],
    items: list[dict[str, Any]],
    validator_contract: dict[str, Any],
    stage12470_summary: dict[str, Any],
    stage12472_summary: dict[str, Any],
) -> list[str]:
    blockers: list[str] = []
    for prefix, issues in [
        ("stage12472_augmented_items", item_issues),
        ("stage12468_validator_contract", contract_issues),
        ("stage12470_summary", stage12470_issues),
        ("stage12472_summary", stage12472_issues),
    ]:
        blockers.extend(f"{prefix}_{key}" for key in issues)

    if validator_contract.get("stage") != STAGE12468:
        blockers.append("stage12468_validator_contract_unexpected_stage")
    if validator_contract.get("record_type") != "stage12468_private_return_validator_contract_v1":
        blockers.append("stage12468_validator_contract_unexpected_record_type")
    if validator_contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        blockers.append("stage12468_required_status_family_mismatch")
    contract_input_path = (validator_contract.get("inputs") or {}).get(
        "optional_private_return_jsonl"
    )
    if contract_input_path != EXPECTED_CONTRACT_RETURN_INPUT:
        blockers.append("stage12468_expected_return_path_unexpected")
    if stage12470_summary.get("stage") != STAGE12470:
        blockers.append("stage12470_summary_unexpected_stage")
    if stage12472_summary.get("stage") != STAGE12472:
        blockers.append("stage12472_summary_unexpected_stage")
    if stage12472_summary.get("locator_augmented_work_item_count") != len(items):
        blockers.append("stage12472_augmented_work_item_count_mismatch")
    if stage12472_summary.get("guardrail_scan_passed") is not True:
        blockers.append("stage12472_guardrail_scan_not_passed")
    if stage12472_summary.get("raw_leak_count") != 0:
        blockers.append("stage12472_raw_leak_count_not_zero")
    for key, expected in FALSE_GUARDS.items():
        if stage12472_summary.get(key) is not expected:
            blockers.append(f"stage12472_{key}_not_false")
    for key, expected in ZERO_GUARDS.items():
        if stage12472_summary.get(key) != expected:
            blockers.append(f"stage12472_{key}_not_{expected}")
    if not items:
        blockers.append("stage12472_augmented_work_items_empty")
    return sorted(set(blockers))


def validate_item(
    item: dict[str, Any],
    locator_fields: list[str],
    validator_contract: dict[str, Any],
    valid_language_labels: set[str],
) -> list[str]:
    reasons: list[str] = []

    for field in locator_fields:
        if not valid_hash(item.get(field)):
            reasons.append(f"locator_field_missing_or_invalid_hash:{field}")

    language_label = item.get("language_family_label")
    if item.get("candidate_language_verified") is not True:
        reasons.append("language_family_label_not_verified")
    if language_label not in valid_language_labels:
        reasons.append("language_family_label_missing_or_invalid")
    item_valid_labels = item.get("valid_language_labels")
    if isinstance(item_valid_labels, list):
        if sorted(item_valid_labels) != sorted(valid_language_labels):
            reasons.append("valid_language_labels_do_not_match_stage12468")
    else:
        reasons.append("valid_language_labels_missing")
    if item.get("expected_return_language_family_label_must_be_verified") is not True:
        reasons.append("expected_return_language_verification_flag_not_true")

    if item.get("locator_is_proof") is not False:
        reasons.append("locator_is_proof_not_false")
    if item.get("locator_augmented") is not True:
        reasons.append("locator_augmented_not_true")
    if item.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
        reasons.append("requested_status_family_not_external_comparable_fail_to_pass")

    for key, expected in FALSE_GUARDS.items():
        if item.get(key) is not expected:
            reasons.append(f"{key}_not_false")
    for key, expected in ZERO_GUARDS.items():
        if item.get(key) != expected:
            reasons.append(f"{key}_not_{expected}")

    contract_inputs = validator_contract.get("inputs") or {}
    expected_return_path = contract_inputs.get("optional_private_return_jsonl")
    if item.get("expected_return_path") != expected_return_path:
        reasons.append("expected_return_path_does_not_match_stage12468_contract")
    if item.get("return_must_be_validator_compatible_with_stage") != STAGE12468:
        reasons.append("return_validator_stage_mismatch")

    contract_return_fields = validator_contract.get("required_return_fields")
    if not isinstance(contract_return_fields, list) or not contract_return_fields:
        reasons.append("stage12468_required_return_fields_missing")
        contract_return_fields = []
    missing_return_fields = subset_missing(contract_return_fields, item.get("required_return_fields"))
    for field in missing_return_fields:
        reasons.append(f"required_return_field_missing:{field}")

    contract_allowed_keys = validator_contract.get("allowed_return_top_level_keys")
    if isinstance(contract_allowed_keys, list):
        missing_allowed_keys = subset_missing(contract_allowed_keys, item.get("allowed_return_top_level_keys"))
        for field in missing_allowed_keys:
            reasons.append(f"allowed_return_top_level_key_missing:{field}")

    combined_slots = required_combined_slots(item, validator_contract)
    if not combined_slots:
        reasons.append("stage12468_required_slots_missing")
    for field_name in ("required_common_slots", "required_combined_slots"):
        missing_slots = subset_missing(
            validator_contract.get("required_proof_slots")
            if isinstance(validator_contract.get("required_proof_slots"), list)
            else [],
            item.get(field_name),
        )
        for slot in missing_slots:
            reasons.append(f"{field_name}_missing_contract_slot:{slot}")

    missing_combined_slots = subset_missing(combined_slots, item.get("required_combined_slots"))
    for slot in missing_combined_slots:
        reasons.append(f"required_combined_slot_missing:{slot}")

    lane_slots_by_ref = validator_contract.get("lane_specific_required_proof_slots")
    lane_slots = []
    if isinstance(lane_slots_by_ref, dict):
        raw_lane_slots = lane_slots_by_ref.get(item.get("lane_ref"))
        if isinstance(raw_lane_slots, list):
            lane_slots = unique_ordered(raw_lane_slots)
    if not lane_slots:
        reasons.append("lane_specific_required_slots_missing_for_lane")
    for slot in subset_missing(lane_slots, item.get("required_lane_specific_slots")):
        reasons.append(f"required_lane_specific_slot_missing:{slot}")

    for slot in subset_missing(REQUIRED_EXPLICIT_PRESENT_SLOTS, item.get("required_explicit_present_slots")):
        reasons.append(f"required_explicit_present_slot_missing:{slot}")

    if item.get("slot_status_required_literal") != "present":
        reasons.append("slot_status_required_literal_not_present")
    placeholder_rules = item.get("slot_hash_placeholder_rejection_rules")
    if not isinstance(placeholder_rules, list) or len(placeholder_rules) < 4:
        reasons.append("slot_hash_placeholder_rejection_rules_missing")

    return sorted(set(reasons))


def accepted_ref(
    item: dict[str, Any],
    locator_fields: list[str],
    validator_contract: dict[str, Any],
) -> dict[str, Any]:
    locator_bundle = {field: item.get(field) for field in locator_fields}
    return {
        "record_type": "stage12473_accepted_locator_work_item_ref_hash_only_v1",
        "work_order_item_ref_hash": item.get("work_order_item_ref_hash"),
        "proof_request_ref_hash": item.get("proof_request_ref_hash"),
        "proof_request_id_hash": item.get("proof_request_id")
        if valid_hash(item.get("proof_request_id"))
        else stable_hash(item.get("proof_request_id")),
        "lane_ref_hash": item.get("lane_ref_hash") or stable_hash(item.get("lane_ref")),
        "language_family_label_hash": stable_hash(item.get("language_family_label")),
        "locator_bundle_ref_hash": stable_hash(locator_bundle),
        "required_return_fields_ref_hash": stable_hash(item.get("required_return_fields")),
        "required_combined_slots_ref_hash": stable_hash(item.get("required_combined_slots")),
        "validator_contract_ref_hash": stable_hash(validator_contract),
        "actionability_status": "accepted_locator_work_item_preflight_passed",
        "candidate_language_verified": True,
        "locator_is_proof": False,
        "required_locator_field_count": len(locator_fields),
        "required_return_field_count": len(item.get("required_return_fields") or []),
        "required_combined_slot_count": len(item.get("required_combined_slots") or []),
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def blocked_ref(item: dict[str, Any], reasons: list[str]) -> dict[str, Any]:
    return {
        "record_type": "stage12473_blocked_locator_work_item_ref_hash_only_v1",
        "work_order_item_ref_hash": item.get("work_order_item_ref_hash")
        if valid_hash(item.get("work_order_item_ref_hash"))
        else stable_hash({"line": item.get("_stage12473_input_line_index")}),
        "proof_request_ref_hash": item.get("proof_request_ref_hash")
        if valid_hash(item.get("proof_request_ref_hash"))
        else stable_hash(item.get("proof_request_ref_hash")),
        "proof_request_id_hash": item.get("proof_request_id")
        if valid_hash(item.get("proof_request_id"))
        else stable_hash(item.get("proof_request_id")),
        "lane_ref_hash": item.get("lane_ref_hash") or stable_hash(item.get("lane_ref")),
        "reason_codes": sorted(set(reasons)),
        "reason_hashes": [stable_hash(reason) for reason in sorted(set(reasons))],
        "actionability_status": "blocked_locator_work_item_preflight_failed",
        "locator_is_proof": False,
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }


def language_counts(items: list[dict[str, Any]], accepted_hashes: set[str]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        if item.get("work_order_item_ref_hash") not in accepted_hashes:
            continue
        label = item.get("language_family_label")
        if isinstance(label, str) and label:
            counts[label] += 1
    return dict(sorted(counts.items()))


def priority_language_counts(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for item in items:
        label = item.get("language_priority_hint") or item.get("language_family_label")
        if isinstance(label, str) and label:
            counts[label] += 1
    return dict(sorted(counts.items()))


def main() -> int:
    items, item_issues = read_jsonl(STAGE12472_AUGMENTED_IN)
    upstream_blocked_items, upstream_blocked_issues = read_jsonl(STAGE12472_BLOCKED_IN)
    stage12472_summary, stage12472_issues = read_json(STAGE12472_SUMMARY)
    stage12470_summary, stage12470_issues = read_json(STAGE12470_SUMMARY)
    validator_contract, contract_issues = read_json(VALIDATOR_CONTRACT_IN)

    locator_fields = required_locator_fields(stage12470_summary)
    valid_language_labels_raw = validator_contract.get("valid_language_labels")
    valid_language_labels = {
        value
        for value in valid_language_labels_raw
        if isinstance(value, str) and value
    } if isinstance(valid_language_labels_raw, list) else set()
    if not valid_language_labels:
        valid_language_labels = {"python", "rust", "c_cpp", "web_js_ts_html"}

    stage_blockers = input_blockers(
        item_issues,
        contract_issues,
        stage12470_issues,
        stage12472_issues,
        items,
        validator_contract,
        stage12470_summary,
        stage12472_summary,
    )
    stage_blockers.extend(f"stage12472_blocked_items_{key}" for key in upstream_blocked_issues)
    reported_blocked_count = stage12472_summary.get("blocked_work_item_count")
    if reported_blocked_count != len(upstream_blocked_items):
        stage_blockers.append("stage12472_blocked_work_item_count_mismatch")
    stage_blockers = sorted(set(stage_blockers))

    accepted_rows: list[dict[str, Any]] = []
    blocked_rows: list[dict[str, Any]] = []
    item_reason_counts: Counter[str] = Counter()
    upstream_blocked_reason_counts: Counter[str] = Counter()
    for item in items:
        reasons = validate_item(item, locator_fields, validator_contract, valid_language_labels)
        if stage_blockers:
            reasons.extend(stage_blockers)
        if reasons:
            blocked_rows.append(blocked_ref(item, reasons))
            item_reason_counts.update(sorted(set(reasons)))
        else:
            accepted_rows.append(accepted_ref(item, locator_fields, validator_contract))

    for item in upstream_blocked_items:
        reasons = item.get("blocker_reasons")
        if not isinstance(reasons, list) or not reasons:
            reasons = ["stage12472_blocked_without_reason"]
        normalized_reasons = [
            f"upstream_stage12472:{reason}"
            for reason in reasons
            if isinstance(reason, str) and reason
        ] or ["upstream_stage12472:invalid_blocker_reason"]
        blocked_rows.append(blocked_ref(item, normalized_reasons))
        upstream_blocked_reason_counts.update(sorted(set(normalized_reasons)))

    accepted_item_hashes = {
        row.get("work_order_item_ref_hash")
        for row in accepted_rows
        if isinstance(row.get("work_order_item_ref_hash"), str)
    }

    summary = {
        "stage": STAGE,
        "record_type": "stage12473_locator_augmented_work_order_preflight_summary_v1",
        "decision": (
            "locator_augmented_work_order_preflight_actionable_subset_ready_blocked_items_carried_zero_credit"
            if accepted_rows and not stage_blockers
            else "blocked_locator_augmented_work_order_preflight_zero_credit"
        ),
        "claim_boundary": (
            "Fail-closed locator work-order preflight only. This stage emits "
            "hash-only actionable refs and blocker refs; it performs no private "
            "return execution, hydration, replay, network access, training, "
            "admission, or packaging."
        ),
        "input_stage_refs": [STAGE12472, STAGE12470, STAGE12468],
        "total_source_work_item_count": stage12472_summary.get("work_item_count"),
        "augmented_work_item_count": len(items),
        "input_locator_augmented_work_item_count": len(items),
        "stage12472_reported_work_item_count": stage12472_summary.get("work_item_count"),
        "stage12472_reported_locator_augmented_work_item_count": stage12472_summary.get(
            "locator_augmented_work_item_count"
        ),
        "stage12472_reported_blocked_work_item_count": stage12472_summary.get(
            "blocked_work_item_count"
        ),
        "input_stage12472_blocked_work_item_count": len(upstream_blocked_items),
        "accepted_locator_work_item_ref_count": len(accepted_rows),
        "accepted_locator_work_item_count": len(accepted_rows),
        "actionable_locator_work_item_count": len(accepted_rows),
        "upstream_blocked_work_item_count": len(upstream_blocked_items),
        "blocked_locator_work_item_ref_count": len(blocked_rows),
        "blocked_locator_work_item_count": len(blocked_rows),
        "executor_request_allowed_count": len(accepted_rows),
        "executor_request_must_exclude_blocked_count": len(blocked_rows),
        "actionable_locator_work_item_count_bucket": count_bucket(len(accepted_rows)),
        "required_locator_fields": locator_fields,
        "required_locator_field_count": len(locator_fields),
        "required_return_fields": validator_contract.get("required_return_fields") or [],
        "required_return_field_count": len(validator_contract.get("required_return_fields") or []),
        "required_proof_slots": validator_contract.get("required_proof_slots") or [],
        "required_proof_slot_count": len(validator_contract.get("required_proof_slots") or []),
        "required_explicit_present_slots": REQUIRED_EXPLICIT_PRESENT_SLOTS,
        "valid_language_labels": sorted(valid_language_labels),
        "accepted_language_counts": language_counts(items, accepted_item_hashes),
        "blocked_language_counts": priority_language_counts(upstream_blocked_items),
        "blocked_language_priority_hint_counts": priority_language_counts(upstream_blocked_items),
        "c_cpp_locator_gap": priority_language_counts(upstream_blocked_items).get("c_cpp", 0),
        "required_status_family": EXPECTED_STATUS_FAMILY,
        "return_contract_expected_path_matched": not any(
            "expected_return_path" in reason for reason in item_reason_counts
        )
        and "stage12468_expected_return_path_unexpected" not in stage_blockers,
        "stage_blockers": sorted(set(stage_blockers)),
        "blocker_reason_counts": dict(sorted((item_reason_counts + upstream_blocked_reason_counts).items())),
        "stage12473_schema_reason_counts": dict(sorted(item_reason_counts.items())),
        "upstream_blocked_reason_counts": dict(sorted(upstream_blocked_reason_counts.items())),
        "upstream_blocked_reason_count": sum(upstream_blocked_reason_counts.values()),
        "non_actions": [
            "does_not_execute",
            "does_not_hydrate",
            "does_not_replay",
            "does_not_use_network",
            "does_not_train",
            "does_not_admit",
            "does_not_package",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
        "artifact_refs": {
            "accepted_locator_work_items_ref": "stage12473_accepted_locator_work_items_ref_jsonl",
            "blocked_locator_work_items_ref": "stage12473_blocked_locator_work_items_ref_jsonl",
            "guardrail_scan": "stage12473_guardrail_scan_json",
            "local_summary": "stage12473_local_summary_json",
            "summary": "stage12473_summary_json",
        },
        "input_artifact_hashes": {
            "stage12472_locator_augmented_work_items": file_hash(STAGE12472_AUGMENTED_IN),
            "stage12472_blocked_locator_augmented_requests": file_hash(STAGE12472_BLOCKED_IN),
            "stage12472_summary": file_hash(STAGE12472_SUMMARY),
            "stage12470_summary": file_hash(STAGE12470_SUMMARY),
            "stage12468_validator_contract": file_hash(VALIDATOR_CONTRACT_IN),
        },
    }

    public_payload = {
        "accepted_locator_work_items_ref": accepted_rows,
        "blocked_locator_work_items_ref": blocked_rows,
        "summary": summary,
    }
    scan_issues = public_scan("stage12473_public_artifacts", public_payload)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12473_guardrail_scan_v1",
        "scan_scope": "stage12473_public_summary_and_hash_only_ref_indexes",
        "scan_status": "completed",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:50]],
        "policy": "no_raw_paths_urls_commands_shas_repo_names_diffs_stdout_stderr_or_source",
        "non_actions": [
            "does_not_execute",
            "does_not_hydrate",
            "does_not_replay",
            "does_not_use_network",
            "does_not_train",
            "does_not_admit",
            "does_not_package",
        ],
        **FALSE_GUARDS,
        **ZERO_GUARDS,
    }

    if scan_issues:
        summary["decision"] = "blocked_public_guardrail_scan_failed_zero_credit"
        summary["stage_blockers"] = sorted(
            set([*summary["stage_blockers"], "stage12473_public_guardrail_scan_failed"])
        )
    summary["guardrail_scan_passed"] = guardrail_scan["scan_passed"]
    summary["raw_leak_count"] = guardrail_scan["raw_leak_count"]
    summary["schema_issue_count"] = (
        len(summary["stage_blockers"])
        + sum(item_reason_counts.values())
    )
    summary["artifact_hashes"] = {
        "accepted_locator_work_items_ref": stable_hash(accepted_rows),
        "blocked_locator_work_items_ref": stable_hash(blocked_rows),
        "guardrail_scan": stable_hash(guardrail_scan),
    }
    summary["summary_hash"] = stable_hash(
        {
            "decision": summary["decision"],
            "accepted_locator_work_item_ref_count": len(accepted_rows),
            "blocked_locator_work_item_ref_count": len(blocked_rows),
            "executor_request_allowed_count": len(accepted_rows),
            "executor_request_must_exclude_blocked_count": len(blocked_rows),
            "stage_blockers": summary["stage_blockers"],
            "blocker_reason_counts": summary["blocker_reason_counts"],
            "raw_leak_count": summary["raw_leak_count"],
            "schema_issue_count": summary["schema_issue_count"],
            "upstream_blocked_reason_count": summary["upstream_blocked_reason_count"],
        }
    )

    write_jsonl(ACCEPTED_OUT, accepted_rows)
    write_jsonl(BLOCKED_OUT, blocked_rows)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)

    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": summary["decision"],
                "total_source_work_item_count": stage12472_summary.get("work_item_count"),
                "input_locator_augmented_work_item_count": len(items),
                "augmented_work_item_count": len(items),
                "actionable_locator_work_item_count": len(accepted_rows),
                "blocked_locator_work_item_ref_count": len(blocked_rows),
            "executor_request_allowed_count": len(accepted_rows),
            "executor_request_must_exclude_blocked_count": len(blocked_rows),
                "external_comparable_repair_credit_count": 0,
                "remaining_external_fail_to_pass_gap": EXPECTED_GAP,
                "emitted_training_rows": 0,
                "sealed_eval_rows": 0,
                "guardrail_scan_passed": summary["guardrail_scan_passed"],
                "raw_leak_count": summary["raw_leak_count"],
                "schema_issue_count": summary["schema_issue_count"],
                "upstream_blocked_reason_count": summary["upstream_blocked_reason_count"],
            "upstream_blocked_reason_count": summary["upstream_blocked_reason_count"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
