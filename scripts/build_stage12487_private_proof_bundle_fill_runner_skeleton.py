#!/usr/bin/env python3
"""Stage12487 private proof-bundle fill runner skeleton.

This stage consumes Stage12486's hash-only row requirements and emits a
private-executor operator packet plus per-row checklist shards. It deliberately
does not execute tests, hydrate repositories, apply patches, write the private
evidence JSONL, write Stage12468 returns, train, admit, package, or award
credit.

If the target private input already exists, this stage performs public-safe
shape validation only and reports counts plus hash-only reject references. It
never emits raw private values.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
STAGE = "stage12487_private_proof_bundle_fill_runner_skeleton"
OUT_DIR = ROOT / "runs/local/artifacts" / STAGE
SUMMARY_OUT = ROOT / "runs/summaries" / f"{STAGE}.json"

STAGE12483 = "stage12483_private_proof_bundle_acquisition_work_order"
STAGE12485 = "stage12485_private_proof_bundle_executor_v1"
STAGE12486 = "stage12486_private_evidence_fill_work_order_validator"
STAGE12468 = "stage12468_non_bears_patch_effect_private_return_validator"

ROW_REQUIREMENTS = ROOT / "runs/local/artifacts" / STAGE12486 / "private_evidence_row_requirements_ref.jsonl"
STAGE12486_WORK_ORDER = ROOT / "runs/local/artifacts" / STAGE12486 / "private_evidence_fill_work_order.json"
STAGE12486_SUMMARY = ROOT / "runs/local/artifacts" / STAGE12486 / "summary.json"
STAGE12486_VALIDATION = ROOT / "runs/local/artifacts" / STAGE12486 / "private_evidence_input_validation_report.json"
PRIVATE_INPUT = ROOT / "runs/local/artifacts" / STAGE12483 / "private_proof_bundle_evidence_rows.jsonl"

OPERATOR_PACKET_OUT = OUT_DIR / "private_executor_operator_packet.json"
CHECKLIST_ROWS_OUT = OUT_DIR / "private_execution_checklist_rows_ref.jsonl"
VALIDATION_REPORT_OUT = OUT_DIR / "private_input_fail_closed_validation_report.json"
GUARDRAIL_OUT = OUT_DIR / "guardrail_scan.json"
LOCAL_SUMMARY_OUT = OUT_DIR / "summary.json"
SHARDS_DIR = OUT_DIR / "shards"
README_OUT = OUT_DIR / "PRIVATE_PROOF_BUNDLE_FILL_RUNNER_STAGE12487.md"

EXPECTED_ROW_COUNT = 9
EXPECTED_SLOT_COUNT = 28
EXPECTED_STATUS_FAMILY = "external_comparable_fail_to_pass"
EXACT_PRESENT = "present"
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
VALID_LANGUAGE_LABELS = {"python", "rust", "c_cpp", "web_js_ts_html"}
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
    r"output|summary|required|key|keys|rule|rules|flag|flags|checklist|shard|"
    r"gate|gates|packet|literal|label)",
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
            value["_stage12487_input_line_no"] = line_no
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


def public_scan(value: Any, label: str = "stage12487") -> list[str]:
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


def row_checklist(requirement: dict[str, Any], index: int) -> dict[str, Any]:
    slots = [slot for slot in requirement.get("required_stage12468_slots", []) if isinstance(slot, str)]
    ref_values = requirement.get("required_work_item_ref_values")
    if not isinstance(ref_values, dict):
        ref_values = {}
    row_ref = {
        key: ref_values.get(key)
        for key in WORK_ITEM_REF_KEYS
        if isinstance(ref_values.get(key), str) and ref_values.get(key)
    }
    gate_keys = [
        "stage12483_ref_pair_copied_exactly",
        "proof_request_id_lane_ref_language_label_privately_joined",
        "requested_status_family_set_external_comparable_fail_to_pass",
        "slot_statuses_exact_28_keys_all_present",
        "slot_hashes_exact_28_keys_non_placeholder_private_evidence_hashes",
        "before_fail_and_after_patch_pass_status_slots_backed_by_real_evidence",
        "same_source_same_verifier_identity_backed_by_real_evidence",
        "verifier_relevance_and_ordered_patch_before_pass_causality_backed_by_real_evidence",
        "anti_leak_public_rendering_and_protected_overlap_evidence_pass",
        "all_zero_credit_and_non_execution_flags_false",
        "blocker_codes_empty_only_for_complete_rows",
        "no_raw_private_values_in_public_logs_or_return_fields",
    ]
    return {
        "record_type": "stage12487_private_execution_checklist_row_ref_hash_only_v1",
        "checklist_row_ref_hash": stable_hash({"index": index, "requirement": requirement.get("requirement_ref_hash")}),
        "source_requirement_ref_hash": requirement.get("requirement_ref_hash"),
        "source_stage12483_work_item_ref_hash": requirement.get("source_stage12483_work_item_ref_hash"),
        "required_work_item_ref_values": row_ref,
        "target_private_input_record_type": requirement.get("target_private_input_record_type"),
        "target_private_input_path_ref": requirement.get("target_private_input_path_ref"),
        "required_private_inputs": [
            "private_mapping_from_stage12483_ref_pair_to_stage12467_proof_request_id",
            "private_mapping_from_stage12483_ref_pair_to_stage12467_lane_ref",
            "private_language_family_label_for_the_same_request",
            "real_private_evidence_for_each_stage12468_required_slot",
            "private_hashes_for_each_slot_evidence_value_without_public_raw_value_disclosure",
        ],
        "per_row_completion_gates": gate_keys,
        "completion_gate_count": len(gate_keys),
        "required_stage12468_slot_count": len(slots),
        "required_stage12468_slots": slots,
        "required_slot_status_literal": EXACT_PRESENT,
        "required_slot_hash_rule": requirement.get("required_slot_hash_rule"),
        "must_set_true": ["proof_complete", "anti_leak_pass"],
        "must_set_false": FALSE_FLAGS,
        "must_set_empty": ["blocker_codes"],
        "submit_rule": "submit_no_row_until_every_gate_is_satisfied_for_this_requirement",
        "hard_reject_if_any_gate_incomplete": True,
        "must_not_emit_public_raw_values": True,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
    }


def validate_existing_private_input(
    rows: list[dict[str, Any]],
    read_issues: Counter[str],
    requirements: list[dict[str, Any]],
    allowed_keys: set[str],
    required_slots: list[str],
) -> tuple[dict[str, Any], Counter[str]]:
    valid_pairs = {
        (
            req.get("required_work_item_ref_values", {}).get("proof_bundle_work_item_ref_hash"),
            req.get("required_work_item_ref_values", {}).get("work_order_item_ref_hash"),
        )
        for req in requirements
        if isinstance(req.get("required_work_item_ref_values"), dict)
    }
    valid_refs = {value for pair in valid_pairs for value in pair if isinstance(value, str)}
    reason_counts: Counter[str] = Counter(read_issues)
    rejected: list[dict[str, Any]] = []
    accepted_count = 0
    seen_pairs: set[tuple[str, str]] = set()

    for row in rows:
        public_row = {key: value for key, value in row.items() if not key.startswith("_stage12487_")}
        reasons: list[str] = []
        extra_keys = set(public_row) - allowed_keys - set(WORK_ITEM_REF_KEYS)
        if extra_keys:
            reasons.append("unapproved_top_level_keys_present")
        ref_pair = tuple(public_row.get(key) for key in WORK_ITEM_REF_KEYS)
        if ref_pair in seen_pairs:
            reasons.append("duplicate_stage12483_ref_pair")
        seen_pairs.add(ref_pair)
        if ref_pair not in valid_pairs:
            reasons.append("stage12483_ref_pair_unknown_or_mismatched")
        for key in WORK_ITEM_REF_KEYS:
            value = public_row.get(key)
            if not isinstance(value, str) or not value:
                reasons.append(f"{key}_missing")
            elif value not in valid_refs:
                reasons.append(f"{key}_unknown")
        if public_row.get("requested_status_family") != EXPECTED_STATUS_FAMILY:
            reasons.append("requested_status_family_invalid")
        if public_row.get("language_family_label") not in VALID_LANGUAGE_LABELS:
            reasons.append("language_family_label_invalid")
        for key in ["proof_request_id", "lane_ref", "language_family_label"]:
            if not isinstance(public_row.get(key), str) or not public_row.get(key):
                reasons.append(f"{key}_missing")
        if public_row.get("proof_complete") is not True:
            reasons.append("proof_complete_not_true")
        if public_row.get("anti_leak_pass") is not True:
            reasons.append("anti_leak_pass_not_true")
        if public_row.get("blocker_codes") not in (None, []):
            reasons.append("blocker_codes_present")
        statuses = public_row.get("slot_statuses")
        hashes = public_row.get("slot_hashes")
        if not isinstance(statuses, dict):
            reasons.append("slot_statuses_not_object")
            statuses = {}
        if not isinstance(hashes, dict):
            reasons.append("slot_hashes_not_object")
            hashes = {}
        if set(statuses) != set(required_slots):
            reasons.append("slot_status_key_set_not_exact_stage12468_slots")
        if set(hashes) != set(required_slots):
            reasons.append("slot_hash_key_set_not_exact_stage12468_slots")
        for slot in required_slots:
            if statuses.get(slot) != EXACT_PRESENT:
                reasons.append(f"slot_status_not_present:{slot}")
            if is_placeholder_hash(hashes.get(slot)):
                reasons.append(f"slot_hash_missing_or_placeholder:{slot}")
        for key in FALSE_FLAGS:
            if public_row.get(key) is not False:
                reasons.append(f"{key}_not_false")
        if public_scan(public_row, f"private_input_line_{row.get('_stage12487_input_line_no')}"):
            reasons.append("public_raw_or_forbidden_pattern_scan_failed")
        if reasons:
            reason_counts.update(reasons)
            rejected.append(
                {
                    "record_type": "stage12487_private_input_rejected_ref_hash_only_v1",
                    "input_line_hash": stable_hash(
                        {
                            "line_no": row.get("_stage12487_input_line_no"),
                            "proof_bundle_work_item_ref_hash": public_row.get("proof_bundle_work_item_ref_hash"),
                            "work_order_item_ref_hash": public_row.get("work_order_item_ref_hash"),
                            "proof_request_id_hash": stable_hash(public_row.get("proof_request_id")),
                        }
                    ),
                    "reason_codes": sorted(set(reasons))[:80],
                }
            )
        else:
            accepted_count += 1

    report = {
        "stage": STAGE,
        "record_type": "stage12487_private_input_fail_closed_validation_report_v1",
        "private_input_present": PRIVATE_INPUT.exists(),
        "private_input_row_count": len(rows),
        "expected_private_input_row_count": EXPECTED_ROW_COUNT,
        "accepted_shape_only_row_count": accepted_count,
        "rejected_shape_only_row_count": len(rejected),
        "all_9_rows_shape_complete": accepted_count == EXPECTED_ROW_COUNT and not rejected,
        "rejected_private_input_refs": rejected,
        "reason_counts": dict(sorted(reason_counts.items())),
        "validation_scope": "public_safe_shape_only_no_raw_value_emission",
        "raw_value_emitted": False,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
    }
    return report, reason_counts


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    work_order, work_order_issues = read_json(STAGE12486_WORK_ORDER)
    stage12486_summary, summary_issues = read_json(STAGE12486_SUMMARY)
    stage12486_validation, validation_issues = read_json(STAGE12486_VALIDATION)
    requirements, requirement_issues = read_jsonl(ROW_REQUIREMENTS)

    upstream_issues: Counter[str] = Counter()
    upstream_issues.update(work_order_issues)
    upstream_issues.update(summary_issues)
    upstream_issues.update(validation_issues)
    upstream_issues.update(requirement_issues)

    required_slots = [
        slot
        for slot in work_order.get("required_stage12468_slots", [])
        if isinstance(slot, str) and slot
    ]
    allowed_return_keys = {
        key
        for key in work_order.get("allowed_return_keys", [])
        if isinstance(key, str) and key
    }
    if len(requirements) != EXPECTED_ROW_COUNT:
        upstream_issues["stage12486_row_requirement_count_not_9"] += 1
    if stage12486_summary.get("row_requirement_count") != EXPECTED_ROW_COUNT:
        upstream_issues["stage12486_summary_row_requirement_count_not_9"] += 1
    if stage12486_summary.get("guardrail_scan_passed") is not True:
        upstream_issues["stage12486_guardrail_not_passed"] += 1
    if stage12486_summary.get("raw_leak_count") != 0:
        upstream_issues["stage12486_raw_leak_count_not_zero"] += 1
    if stage12486_summary.get("upstream_issue_count") != 0:
        upstream_issues["stage12486_upstream_issue_count_not_zero"] += 1
    if stage12486_validation.get("accepted_shape_only_row_count", 0) > EXPECTED_ROW_COUNT:
        upstream_issues["stage12486_validation_accepted_count_over_9"] += 1
    if len(required_slots) != EXPECTED_SLOT_COUNT:
        upstream_issues["required_stage12468_slot_count_not_28"] += 1
    if work_order.get("required_status_family") != EXPECTED_STATUS_FAMILY:
        upstream_issues["required_status_family_invalid"] += 1
    if work_order.get("required_private_only_work_item_ref_keys") != WORK_ITEM_REF_KEYS:
        upstream_issues["work_item_ref_key_contract_mismatch"] += 1

    checklist_rows = [] if upstream_issues else [
        row_checklist(requirement, index)
        for index, requirement in enumerate(requirements, 1)
    ]

    private_rows: list[dict[str, Any]] = []
    private_read_issues: Counter[str] = Counter()
    if PRIVATE_INPUT.exists():
        private_rows, private_read_issues = read_jsonl(PRIVATE_INPUT)
    else:
        private_read_issues["private_input_file_missing"] += 1
    validation_report, validation_reason_counts = validate_existing_private_input(
        private_rows,
        private_read_issues,
        requirements,
        allowed_return_keys,
        required_slots,
    )

    operator_packet = {
        "stage": STAGE,
        "record_type": "stage12487_private_executor_operator_packet_v1",
        "source_stage_refs": [STAGE12486, STAGE12483, STAGE12485, STAGE12468],
        "target_private_input_path": str(PRIVATE_INPUT.relative_to(ROOT)),
        "target_private_input_record_type": "stage12485_private_proof_bundle_evidence_row_candidate_v1",
        "objective": "fill_stage12483_private_proof_bundle_evidence_rows_jsonl_for_all_9_stage12486_requirements",
        "runner_mode": "operator_packet_and_checklist_only_no_execution",
        "required_executor_inputs": [
            "access_to_private_stage12483_work_order_context_for_the_exact_ref_pairs",
            "access_to_private_stage12467_request_mapping_for_proof_request_id_lane_ref_language_label",
            "access_to_real_private_before_state_after_or_solution_state_patch_and_verifier_artifacts",
            "ability_to_compute_private_evidence_hashes_without_public_raw_value_disclosure",
            "permission_to_write_only_the_target_private_input_jsonl_when_all_per_row_gates_are_complete",
        ],
        "private_input_write_policy": [
            "write_one_json_object_per_completed_row_only",
            "do_not_write_partial_rows",
            "do_not_include_raw_paths_commands_outputs_diffs_source_urls_or_private_text",
            "include_only_stage12485_allowed_return_keys_plus_stage12483_ref_keys",
            "rerun_stage12486_or_stage12487_for_shape_check_before_stage12485",
        ],
        "per_row_completion_gates_are_authoritative": True,
        "row_checklist_count": len(checklist_rows),
        "shard_count": (len(checklist_rows) + 2) // 3,
        "required_stage12468_slot_count": len(required_slots),
        "required_stage12468_slots": required_slots,
        "required_status_family": EXPECTED_STATUS_FAMILY,
        "allowed_return_keys": sorted(allowed_return_keys),
        "hard_stop_conditions": [
            "any_stage12483_ref_pair_unknown_or_mismatched",
            "any_required_slot_missing_or_placeholder",
            "any_before_fail_or_after_patch_pass_status_not_real",
            "same_verifier_identity_missing",
            "verifier_relevance_or_ordered_causality_missing",
            "raw_private_value_would_be_emitted_publicly",
            "training_admission_packaging_credit_or_execution_flags_not_false",
        ],
        "non_actions": [
            "stage12487_does_not_execute_tests",
            "stage12487_does_not_hydrate_repositories",
            "stage12487_does_not_apply_patches",
            "stage12487_does_not_write_private_input_rows",
            "stage12487_does_not_write_stage12468_official_return_file",
            "stage12487_does_not_train_admit_package_or_credit",
        ],
        "input_artifact_hashes": {
            "stage12486_row_requirements": file_hash(ROW_REQUIREMENTS),
            "stage12486_work_order": file_hash(STAGE12486_WORK_ORDER),
            "stage12486_summary": file_hash(STAGE12486_SUMMARY),
            "stage12486_validation_report": file_hash(STAGE12486_VALIDATION),
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

    payload_for_scan = {
        "operator_packet": operator_packet,
        "checklist_rows": checklist_rows,
        "validation_report": validation_report,
    }
    scan_issues = public_scan(payload_for_scan)
    guardrail_scan = {
        "stage": STAGE,
        "record_type": "stage12487_guardrail_scan_v1",
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

    if scan_issues:
        checklist_rows = []
        operator_packet["row_checklist_count"] = 0
        operator_packet["shard_count"] = 0

    decision = (
        "private_input_shape_complete_rerun_stage12485_no_execution_zero_credit"
        if validation_report["all_9_rows_shape_complete"] and guardrail_scan["scan_passed"] and not upstream_issues
        else "operator_packet_ready_private_input_missing_or_incomplete_zero_credit"
        if guardrail_scan["scan_passed"] and not upstream_issues
        else "blocked_stage12487_upstream_or_guardrail_issue_zero_credit"
    )
    summary = {
        "stage": STAGE,
        "record_type": "stage12487_private_proof_bundle_fill_runner_skeleton_summary_v1",
        "decision": decision,
        "source_stage_refs": [STAGE12486, STAGE12483, STAGE12485, STAGE12468],
        "operator_packet_generated": bool(checklist_rows) and guardrail_scan["scan_passed"],
        "checklist_row_count": len(checklist_rows),
        "checklist_shard_count": (len(checklist_rows) + 2) // 3,
        "row_requirement_count": len(requirements),
        "required_stage12468_slot_count": len(required_slots),
        "private_input_present": PRIVATE_INPUT.exists(),
        "private_input_row_count": len(private_rows),
        "accepted_shape_only_row_count": validation_report["accepted_shape_only_row_count"],
        "rejected_shape_only_row_count": validation_report["rejected_shape_only_row_count"],
        "upstream_issue_count": sum(upstream_issues.values()),
        "upstream_issues": dict(sorted(upstream_issues.items())),
        "validation_reason_counts": dict(sorted(validation_reason_counts.items())),
        "guardrail_scan_passed": guardrail_scan["scan_passed"],
        "raw_leak_count": guardrail_scan["raw_leak_count"],
        "official_stage12468_return_file_written": False,
        "training_rows_emitted": 0,
        "training_allowed": False,
        "admission_allowed": False,
        "packaging_allowed": False,
        "execution_performed_by_stage": False,
        "hydration_performed_by_stage": False,
        "replay_performed_by_stage": False,
        "external_repair_credit_count": 0,
        "next_action": "private_executor_fill_target_jsonl_then_rerun_stage12485",
        "summary_hash": stable_hash(
            {
                "decision": decision,
                "checklist_rows": len(checklist_rows),
                "private_rows": len(private_rows),
                "accepted_shape": validation_report["accepted_shape_only_row_count"],
                "raw_leak_count": guardrail_scan["raw_leak_count"],
            }
        ),
    }

    write_json(OPERATOR_PACKET_OUT, operator_packet)
    write_jsonl(CHECKLIST_ROWS_OUT, checklist_rows)
    SHARDS_DIR.mkdir(parents=True, exist_ok=True)
    for index in range(0, len(checklist_rows), 3):
        shard_rows = checklist_rows[index:index + 3]
        write_json(
            SHARDS_DIR / f"private_execution_checklist_shard_{index // 3 + 1:02d}.json",
            {
                "stage": STAGE,
                "record_type": "stage12487_private_execution_checklist_shard_v1",
                "shard_index": index // 3 + 1,
                "checklist_row_count": len(shard_rows),
                "rows": shard_rows,
                "training_allowed": False,
                "admission_allowed": False,
                "packaging_allowed": False,
                "execution_performed_by_stage": False,
                "hydration_performed_by_stage": False,
                "replay_performed_by_stage": False,
                "external_repair_credit_count": 0,
            },
        )
    write_json(VALIDATION_REPORT_OUT, validation_report)
    write_json(GUARDRAIL_OUT, guardrail_scan)
    write_json(LOCAL_SUMMARY_OUT, summary)
    write_json(SUMMARY_OUT, summary)
    README_OUT.write_text(
        "# Stage12487 Private Proof Bundle Fill Runner Skeleton\n\n"
        "This packet is an operator checklist only. It does not execute tests, hydrate repositories, "
        "apply patches, write private rows, train, admit, package, or award credit.\n\n"
        + json.dumps(summary, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "stage": STAGE,
                "decision": decision,
                "operator_packet_generated": summary["operator_packet_generated"],
                "checklist_row_count": len(checklist_rows),
                "checklist_shard_count": summary["checklist_shard_count"],
                "required_stage12468_slot_count": len(required_slots),
                "private_input_present": PRIVATE_INPUT.exists(),
                "private_input_row_count": len(private_rows),
                "accepted_shape_only_row_count": validation_report["accepted_shape_only_row_count"],
                "rejected_shape_only_row_count": validation_report["rejected_shape_only_row_count"],
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
