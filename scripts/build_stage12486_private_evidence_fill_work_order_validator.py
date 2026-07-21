#!/usr/bin/env python3
"""Stage12486 private evidence fill work-order and validator helper.

This helper advances the Stage12483 -> Stage12485 -> Stage12468 path without
performing private execution. It publishes a public-safe work-order for the
private executor that must create Stage12485's optional private input file:

  runs/local/artifacts/stage12483_private_proof_bundle_acquisition_work_order/
    private_proof_bundle_evidence_rows.jsonl

If that private file already exists, this script validates only its public-safe
shape and emits hash/status/count reports. It never emits raw paths, commands,
outputs, diffs, source content, training rows, admissions, or repair credit.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12486_private_evidence_fill_work_order_validator"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12483 = "stage12483_private_proof_bundle_acquisition_work_order"
STAGE12485 = "stage12485_private_proof_bundle_executor_v1"
STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"

WORK_ITEMS = ROOT / "runs/local/artifacts" / STAGE12483 / "private_proof_bundle_work_items_ref.jsonl"
PRIVATE_INPUT = ROOT / "runs/local/artifacts" / STAGE12483 / "private_proof_bundle_evidence_rows.jsonl"
STAGE12483_SUMMARY = ROOT / "runs/local/artifacts" / STAGE12483 / "summary.json"
STAGE12485_CONTRACT = ROOT / "runs/local/artifacts" / STAGE12485 / "private_input_contract.json"
STAGE12468_CONTRACT = ROOT / "runs/local/artifacts" / STAGE12468 / "validator_contract.json"

WORK_ORDER_OUT = OUT_DIR / "private_evidence_fill_work_order.json"
ROW_REQUIREMENTS_OUT = OUT_DIR / "private_evidence_row_requirements_ref.jsonl"
VALIDATION_REPORT_OUT = OUT_DIR / "private_evidence_input_validation_report.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"

EXPECTED_WORK_ITEM_COUNT = 9
EXPECTED_SLOT_COUNT = 28
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
EXACT_PRESENT = "present"
VALID_LANGUAGE_LABELS = {"python", "rust", "c_cpp", "web_js_ts_html"}
WORK_ITEM_REF_KEYS = ["proof_bundle_work_item_ref_hash", "work_order_item_ref_hash"]
FALSE_FLAGS = [
    "training_after_return_allowed",
    "admission_after_return_allowed",
    "packaging_after_return_allowed",
    "external_repair_credit_after_return_allowed",
    "execution_performed_by_stage",
    "hydration_performed_by_stage",
    "replay_performed_by_stage",
]
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
    r"candidate|input|contract|private|work|order|row|validator|executor|file|"
    r"output|summary|required|key|keys|rule|rules|flag|flags)",
    re.IGNORECASE,
)
RAW_LEAK_RE = re.compile(
    r"https?://|www\.|diff --git|@@ |^\+\+\+ |^--- |<<<<<<<|>>>>>>>|"
    r"(?<![A-Za-z0-9_])/(?:[A-Za-z0-9._-]+/){2,}[A-Za-z0-9._-]+|"
    r"\b(?:git clone|git apply|pytest\s|python -c|bash -|sh -|curl\s|"
    r"stdout|stderr|traceback|terminal output|command output)\b",
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
                issues["invalid_json"] += 1
                continue
            if not isinstance(value, dict):
                issues["row_not_object"] += 1
                continue
            value["_stage12486_input_line_no"] = line_no
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


def is_hash_candidate(value: str) -> bool:
    return bool(
        re.fullmatch(
            r"(?:[0-9a-f]{24}|[0-9a-f]{32}|[0-9a-f]{40}|[0-9a-f]{64}|sha256:[0-9a-f]{64})",
            value.strip().lower(),
        )
    )


def is_placeholder_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    normalized = value.strip().lower().replace("-", "_").replace("/", "_")
    if normalized in PLACEHOLDER_VALUES:
        return True
    if not is_hash_candidate(value):
        return True
    compact = re.sub(r"[^A-Za-z0-9]", "", value.strip())
    return bool(compact) and len(set(compact.lower())) == 1


def public_scan(value: Any, label: str = "stage12486") -> list[str]:
    issues: list[str] = []
    leaf = label.rsplit(".", 1)[-1].split("[", 1)[0].lower()
    if leaf in FORBIDDEN_PUBLIC_KEYS and not PUBLIC_SAFE_KEY_RE.search(label):
        issues.append(f"{label}:forbidden_public_key")
    if isinstance(value, str):
        if RAW_LEAK_RE.search(value):
            issues.append(f"{label}:raw_content_pattern:{stable_hash(value)}")
    elif isinstance(value, dict):
        for key, child in value.items():
            issues.extend(public_scan(child, f"{label}.{key}"))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            issues.extend(public_scan(child, f"{label}[{index}]"))
    return issues


def row_requirement(item: dict[str, Any], required_slots: list[str], allowed_return_keys: list[str]) -> dict[str, Any]:
    return {
        "record_type": "stage12486_private_evidence_row_requirement_ref_hash_only_v1",
        "requirement_ref_hash": stable_hash(
            {
                "proof_bundle_work_item_ref_hash": item.get("proof_bundle_work_item_ref_hash"),
                "work_order_item_ref_hash": item.get("work_order_item_ref_hash"),
            }
        ),
        "source_stage12483_work_item_ref_hash": item.get("proof_bundle_work_item_ref_hash"),
        "required_private_only_work_item_ref_keys": WORK_ITEM_REF_KEYS,
        "required_work_item_ref_values": {
            key: item.get(key)
            for key in WORK_ITEM_REF_KEYS
        },
        "target_private_input_record_type": "stage12485_private_proof_bundle_evidence_row_candidate_v1",
        "target_private_input_path_ref": "stage12483_private_proof_bundle_evidence_rows_jsonl",
        "allowed_top_level_return_keys": allowed_return_keys,
        "required_stage12468_slot_count": len(required_slots),
        "required_stage12468_slots": required_slots,
        "required_slot_status_literal": EXACT_PRESENT,
        "required_slot_hash_rule": "24_32_40_64_hex_or_sha256_colon_64_hex_non_placeholder_hash_of_private_evidence_only",
        "must_privately_derive_and_fill": [
            "proof_request_id",
            "lane_ref",
            "language_family_label",
            "slot_statuses",
            "slot_hashes",
        ],
        "must_set_false": FALSE_FLAGS,
        "must_set_true": ["proof_complete", "anti_leak_pass"],
        "must_set_empty": ["blocker_codes"],
        "must_not_emit_public_raw_values": True,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "external_repair_credit_count": 0,
    }


def validate_private_row(
    row: dict[str, Any],
    required_slots: list[str],
    allowed_keys: set[str],
    valid_ref_pairs: set[tuple[str, str]],
    valid_refs: set[str],
) -> list[str]:
    reasons: list[str] = []
    line_no = row.get("_stage12486_input_line_no")
    public_row = {key: value for key, value in row.items() if not key.startswith("_stage12486_")}
    extra_keys = set(public_row) - allowed_keys - set(WORK_ITEM_REF_KEYS)
    if extra_keys:
        reasons.append("unapproved_top_level_keys_present")
    ref_values = []
    for key in WORK_ITEM_REF_KEYS:
        value = public_row.get(key)
        if not isinstance(value, str) or not value:
            reasons.append(f"{key}_missing")
        else:
            ref_values.append(value)
            if value not in valid_refs:
                reasons.append(f"{key}_unknown")
    if len(ref_values) == 2 and tuple(ref_values) not in valid_ref_pairs:
        reasons.append("work_item_ref_pair_not_from_same_stage12483_item")
    for key in ["proof_request_id", "lane_ref", "language_family_label"]:
        if not isinstance(public_row.get(key), str) or not public_row.get(key):
            reasons.append(f"{key}_missing")
    if public_row.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
        reasons.append("requested_status_family_invalid")
    if public_row.get("language_family_label") not in VALID_LANGUAGE_LABELS:
        reasons.append("language_family_label_invalid")
    if public_row.get("proof_complete") is not True:
        reasons.append("proof_complete_not_true")
    if public_row.get("anti_leak_pass") is not True:
        reasons.append("anti_leak_pass_not_true")
    if public_row.get("blocker_codes") not in (None, []):
        reasons.append("blocker_codes_present")
    slot_statuses = public_row.get("slot_statuses")
    slot_hashes = public_row.get("slot_hashes")
    if not isinstance(slot_statuses, dict):
        reasons.append("slot_statuses_not_object")
        slot_statuses = {}
    if not isinstance(slot_hashes, dict):
        reasons.append("slot_hashes_not_object")
        slot_hashes = {}
    if set(slot_statuses) != set(required_slots):
        reasons.append("slot_status_key_set_not_exact_stage12468_28_slots")
    if set(slot_hashes) != set(required_slots):
        reasons.append("slot_hash_key_set_not_exact_stage12468_28_slots")
    for slot in required_slots:
        if slot_statuses.get(slot) != EXACT_PRESENT:
            reasons.append(f"slot_status_not_present:{slot}")
        if is_placeholder_hash(slot_hashes.get(slot)):
            reasons.append(f"slot_hash_missing_or_placeholder:{slot}")
    for key in FALSE_FLAGS:
        if public_row.get(key) is not False:
            reasons.append(f"{key}_not_false")
    if public_scan(public_row, f"private_input_line_{line_no}"):
        reasons.append("public_raw_or_forbidden_pattern_scan_failed")
    return reasons


def main() -> int:
    stage12483_summary, s83_issues = read_json(STAGE12483_SUMMARY)
    stage12485_contract, s85_issues = read_json(STAGE12485_CONTRACT)
    stage12468_contract, s68_issues = read_json(STAGE12468_CONTRACT)
    work_items, work_item_issues = read_jsonl(WORK_ITEMS)

    upstream_issues = Counter()
    upstream_issues.update(s83_issues)
    upstream_issues.update(s85_issues)
    upstream_issues.update(s68_issues)
    upstream_issues.update(work_item_issues)

    required_slots = [
        slot
        for slot in stage12468_contract.get("required_proof_slots", stage12485_contract.get("required_proof_slots", []))
        if isinstance(slot, str) and slot
    ]
    allowed_return_keys = sorted(
        {
            key
            for key in stage12485_contract.get(
                "allowed_return_keys",
                stage12468_contract.get("allowed_return_top_level_keys", []),
            )
            if isinstance(key, str) and key
        }
    )
    if len(work_items) != EXPECTED_WORK_ITEM_COUNT:
        upstream_issues["stage12483_work_item_count_not_9"] += 1
    if stage12483_summary.get("proof_bundle_work_item_count") != EXPECTED_WORK_ITEM_COUNT:
        upstream_issues["stage12483_summary_work_item_count_not_9"] += 1
    if len(required_slots) != EXPECTED_SLOT_COUNT:
        upstream_issues["stage12468_required_slot_count_not_28"] += 1
    if stage12468_contract.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        upstream_issues["stage12468_required_status_family_invalid"] += 1
    if stage12485_contract.get("private_only_work_item_ref_keys_required") != WORK_ITEM_REF_KEYS:
        upstream_issues["stage12485_work_item_ref_key_contract_mismatch"] += 1

    row_requirements = [
        row_requirement(item, required_slots, allowed_return_keys)
        for item in work_items
    ] if not upstream_issues else []

    valid_ref_pairs = {
        (item.get("proof_bundle_work_item_ref_hash"), item.get("work_order_item_ref_hash"))
        for item in work_items
        if isinstance(item.get("proof_bundle_work_item_ref_hash"), str)
        and isinstance(item.get("work_order_item_ref_hash"), str)
    }
    valid_refs = {value for pair in valid_ref_pairs for value in pair}

    private_rows: list[dict[str, Any]] = []
    private_issues: Counter[str] = Counter()
    validation_rejected: list[dict[str, Any]] = []
    validation_reason_counts: Counter[str] = Counter()
    accepted_shape_count = 0
    private_input_present = PRIVATE_INPUT.exists()
    if private_input_present:
        private_rows, private_issues = read_jsonl(PRIVATE_INPUT)
        validation_reason_counts.update(private_issues)
        allowed_key_set = set(allowed_return_keys)
        for row in private_rows:
            reasons = validate_private_row(row, required_slots, allowed_key_set, valid_ref_pairs, valid_refs)
            if reasons:
                validation_reason_counts.update(reasons)
                validation_rejected.append(
                    {
                        "record_type": "stage12486_private_evidence_input_rejected_ref_hash_only_v1",
                        "input_line_hash": stable_hash(
                            {
                                "line_no": row.get("_stage12486_input_line_no"),
                                "proof_bundle_work_item_ref_hash": row.get("proof_bundle_work_item_ref_hash"),
                                "work_order_item_ref_hash": row.get("work_order_item_ref_hash"),
                                "proof_request_id_hash": stable_hash(row.get("proof_request_id")),
                            }
                        ),
                        "reason_codes": sorted(set(reasons))[:60],
                    }
                )
            else:
                accepted_shape_count += 1
    else:
        validation_reason_counts["private_input_file_missing"] += 1

    work_order = {
        "stage": STAGE,
        "record_type": "stage12486_private_evidence_fill_work_order_v1",
        "target_private_input_path": str(PRIVATE_INPUT.relative_to(ROOT)),
        "target_stage12485_contract": str(STAGE12485_CONTRACT.relative_to(ROOT)),
        "target_stage12468_contract": str(STAGE12468_CONTRACT.relative_to(ROOT)),
        "private_executor_objective": "produce_private_proof_bundle_evidence_rows_jsonl_from_all_9_stage12483_work_items",
        "private_executor_must_not_report_raw_values_publicly": True,
        "required_private_only_work_item_ref_keys": WORK_ITEM_REF_KEYS,
        "required_stage12483_work_item_count": EXPECTED_WORK_ITEM_COUNT,
        "required_stage12468_slot_count": len(required_slots),
        "required_stage12468_slots": required_slots,
        "required_status_family": EXPECTED_STATUS_FAMILY,
        "allowed_return_keys": allowed_return_keys,
        "per_row_fill_rules": [
            "copy_exact_stage12483_proof_bundle_work_item_ref_hash_and_work_order_item_ref_hash_into_each_private_row",
            "privately_join_to_the_matching_stage12467_proof_request_id_lane_ref_and_language_family_label",
            "populate_slot_statuses_with_exactly_all_28_stage12468_slots_set_to_present",
            "populate_slot_hashes_with_exactly_all_28_stage12468_slots_using_non_placeholder_hashes_of_real_private_evidence",
            "set_proof_complete_and_anti_leak_pass_true_only_after_all_slots_have_real_private_evidence",
            "set_all_training_admission_packaging_credit_and_execution_hydration_replay_flags_false",
            "leave_blocker_codes_empty_for complete rows; otherwise do not submit the row to Stage12485",
        ],
        "hard_reject_rules": [
            "raw_path_command_output_diff_source_or_url_in_public_fields",
            "missing_any_stage12468_slot",
            "placeholder_claim_or_status_word_as_slot_hash",
            "locator_only_metadata_only_pass_to_pass_selected_test_only_or_cross_source_join_evidence",
            "before_status_not_fail_or_after_patch_status_not_pass",
            "same_verifier_identity_or_verifier_relevance_missing",
        ],
        "non_actions": [
            "stage12486_does_not_execute_private_work",
            "stage12486_does_not_hydrate_sources",
            "stage12486_does_not_apply_patches",
            "stage12486_does_not_write_private_input_rows",
            "stage12486_does_not_write_stage12468_official_return_file",
            "stage12486_does_not_train_admit_package_or_credit",
        ],
        "row_requirement_count": len(row_requirements),
        "upstream_issue_count": sum(upstream_issues.values()),
        "input_artifact_hashes": {
            "stage12483_work_items": file_hash(WORK_ITEMS),
            "stage12483_summary": file_hash(STAGE12483_SUMMARY),
            "stage12485_private_input_contract": file_hash(STAGE12485_CONTRACT),
            "stage12468_validator_contract": file_hash(STAGE12468_CONTRACT),
            "private_input_if_present": file_hash(PRIVATE_INPUT),
        },
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
    }

    validation_report = {
        "stage": STAGE,
        "record_type": "stage12486_private_evidence_input_validation_report_v1",
        "private_input_present": private_input_present,
        "private_input_row_count": len(private_rows),
        "accepted_shape_only_row_count": accepted_shape_count,
        "rejected_shape_only_row_count": len(validation_rejected),
        "expected_private_input_row_count": EXPECTED_WORK_ITEM_COUNT,
        "all_9_rows_shape_complete": accepted_shape_count == EXPECTED_WORK_ITEM_COUNT and not validation_rejected,
        "rejected_private_input_refs": validation_rejected,
        "reason_counts": dict(sorted(validation_reason_counts.items())),
        "raw_value_emitted": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
    }

    payload_for_scan = {
        "work_order": work_order,
        "row_requirements": row_requirements,
        "validation_report": validation_report,
    }
    scan_issues = public_scan(payload_for_scan)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12486_guardrail_scan_v1",
        "scan_passed": not scan_issues,
        "raw_leak_count": len(scan_issues),
        "issue_hashes": [stable_hash(issue) for issue in scan_issues[:80]],
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
    }

    decision = (
        "private_evidence_fill_work_order_ready_all_9_shape_valid_rerun_stage12485"
        if validation_report["all_9_rows_shape_complete"] and guardrail_scan["scan_passed"] and not upstream_issues
        else "private_evidence_fill_work_order_ready_private_input_missing_or_incomplete_zero_credit"
        if guardrail_scan["scan_passed"] and not upstream_issues
        else "blocked_stage12486_public_guardrail_or_upstream_contract_issue_zero_credit"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12486_private_evidence_fill_work_order_validator_summary_v1",
        "decision": decision,
        "source_stage_refs": [STAGE12483, STAGE12485, STAGE12468],
        "work_order_generated": bool(row_requirements) and guardrail_scan["scan_passed"],
        "row_requirement_count": len(row_requirements),
        "stage12483_work_item_count": len(work_items),
        "required_stage12468_slot_count": len(required_slots),
        "required_private_only_work_item_ref_key_count": len(WORK_ITEM_REF_KEYS),
        "private_input_present": private_input_present,
        "private_input_row_count": len(private_rows),
        "accepted_shape_only_row_count": accepted_shape_count,
        "rejected_shape_only_row_count": len(validation_rejected),
        "upstream_issue_count": sum(upstream_issues.values()),
        "upstream_issues": dict(sorted(upstream_issues.items())),
        "guardrail_scan_passed": guardrail_scan["scan_passed"],
        "raw_leak_count": guardrail_scan["raw_leak_count"],
        "next_action": "private_executor_fill_private_proof_bundle_evidence_rows_jsonl_then_rerun_stage12485",
        "training_rows_emitted": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
        "summary_hash": stable_hash(
            {
                "decision": decision,
                "rows": len(row_requirements),
                "slots": len(required_slots),
                "private_rows": len(private_rows),
                "accepted_shape": accepted_shape_count,
                "raw_leak_count": guardrail_scan["raw_leak_count"],
            }
        ),
    }

    write_json(WORK_ORDER_OUT, work_order)
    write_jsonl(ROW_REQUIREMENTS_OUT, row_requirements)
    write_json(VALIDATION_REPORT_OUT, validation_report)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": decision,
                "work_order_generated": summary["work_order_generated"],
                "row_requirement_count": len(row_requirements),
                "required_stage12468_slot_count": len(required_slots),
                "private_input_present": private_input_present,
                "private_input_row_count": len(private_rows),
                "guardrail_scan_passed": guardrail_scan["scan_passed"],
                "raw_leak_count": guardrail_scan["raw_leak_count"],
                "training_allowed": False,
                "admission_allowed": False,
                "external_repair_credit_count": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
